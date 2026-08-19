#include "transport_esp32.h"
#include "constants_ups.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include <atomic>

#ifdef USE_ESP32

namespace esphome {
namespace ups_hid {

static const char *const ESP32_USB_TAG = "ups_hid.esp32_usb";

// USB HID Class defines
#ifndef USB_CLASS_HID
#define USB_CLASS_HID 0x03
#endif

// Shared completion context for HID GET_REPORT / SET_REPORT control
// transfers (usb_host_transfer_submit_control is asynchronous; these
// functions wrap it synchronously via a semaphore + timeout).
//
// IMPORTANT - why this is heap-allocated with an `abandoned` flag instead
// of a plain stack-local struct:
//
// The original implementation put this context on the caller's stack and
// pointed transfer->context at it. If our local xSemaphoreTake(...) timed
// out, the caller would immediately vSemaphoreDelete() the semaphore and
// usb_host_transfer_free() the transfer, then return - destroying the
// stack frame. But usb_host_transfer_submit_control() is asynchronous: a
// timeout on OUR side does not guarantee the USB Host Library has actually
// abandoned the transfer. If its completion callback fired even slightly
// after we gave up, it would write through a dangling pointer into a
// destroyed stack frame and call xSemaphoreGive() on an already-deleted
// semaphore handle - undefined behavior. In practice, against a
// Megatec/Cypress UPS whose GET_REPORT can legitimately stall, this caused
// heap/USB-host-driver corruption (observed as the protocol registry
// "losing" entries on the next detection attempt, with no clean crash log).
//
// Fix: heap-allocate the context so it outlives the function on timeout,
// and use `abandoned` so whichever side (caller-on-timeout vs.
// callback-on-late-completion) loses the race is the one responsible for
// freeing the semaphore/transfer/context - never both, and never neither.
// Trade-off: if the transfer truly never completes, this leaks a small
// fixed amount of memory (better than memory corruption, and only happens
// on genuine transport-level failures against non-compliant devices).
struct HidTransferCtx {
    SemaphoreHandle_t sem;
    esp_err_t result;
    size_t actual_bytes;
    std::atomic<bool> abandoned{false};
};

// Shared control-transfer completion callback for both GET_REPORT and
// SET_REPORT. If the caller already gave up (abandoned == true), this
// takes over cleanup of the semaphore/transfer/context; otherwise it
// reports the result back to the still-waiting caller as before.
static void hid_control_transfer_callback(usb_transfer_t *t) {
    auto *c = static_cast<HidTransferCtx *>(t->context);
    if (c->abandoned.load()) {
        vSemaphoreDelete(c->sem);
        usb_host_transfer_free(t);
        delete c;
        return;
    }
    c->result = (t->status == USB_TRANSFER_STATUS_COMPLETED) ? ESP_OK : ESP_FAIL;
    c->actual_bytes = t->actual_num_bytes;
    xSemaphoreGive(c->sem);
}

Esp32UsbTransport::Esp32UsbTransport() {
    memset(&device_, 0, sizeof(device_));
}

Esp32UsbTransport::~Esp32UsbTransport() {
    deinitialize();
}

esp_err_t Esp32UsbTransport::initialize() {
    std::lock_guard<std::mutex> lock(device_mutex_);
    
    if (initialized_.load()) {
        return ESP_OK;
    }
    
    ESP_LOGI(ESP32_USB_TAG, "Initializing ESP32 USB transport");
    
    esp_err_t ret = setup_usb_host();
    if (ret != ESP_OK) {
        set_last_error("Failed to setup USB host: " + std::string(esp_err_to_name(ret)));
        return ret;
    }
    
    // Register USB client for device events - connection will be asynchronous  
    ret = find_and_open_device();
    if (ret != ESP_OK) {
        teardown_usb_host();
        return ret;
    }
    
    initialized_ = true;
    
    ESP_LOGI(ESP32_USB_TAG, "ESP32 USB transport initialized - waiting for USB device connection events");
    
    return ESP_OK;
}

esp_err_t Esp32UsbTransport::deinitialize() {
    std::lock_guard<std::mutex> lock(device_mutex_);
    
    if (!initialized_.load()) {
        return ESP_OK;
    }
    
    ESP_LOGI(ESP32_USB_TAG, "Deinitializing ESP32 USB transport");
    
    connected_ = false;
    initialized_ = false;
    
    esp_err_t ret = teardown_usb_host();
    if (ret != ESP_OK) {
        ESP_LOGW(ESP32_USB_TAG, "USB teardown had issues: %s", esp_err_to_name(ret));
    }
    
    return ret;
}

bool Esp32UsbTransport::is_connected() const {
    return connected_.load() && initialized_.load();
}

uint16_t Esp32UsbTransport::get_vendor_id() const {
    std::lock_guard<std::mutex> lock(device_mutex_);
    return device_.vendor_id;
}

uint16_t Esp32UsbTransport::get_product_id() const {
    std::lock_guard<std::mutex> lock(device_mutex_);
    return device_.product_id;
}

esp_err_t Esp32UsbTransport::hid_get_report(uint8_t report_type, uint8_t report_id, 
                                           uint8_t* data, size_t* data_len, 
                                           uint32_t timeout_ms) {
    if (!device_.dev_hdl) {
        ESP_LOGE(ESP32_USB_TAG, "HID GET_REPORT: No device handle");
        return ESP_ERR_INVALID_ARG;
    }
    if (!data || !data_len || *data_len == 0) {
        ESP_LOGE(ESP32_USB_TAG, "HID GET_REPORT: Invalid parameters");
        return ESP_ERR_INVALID_ARG;
    }

    ESP_LOGD(ESP32_USB_TAG, "HID GET_REPORT: type=0x%02X, id=0x%02X, max_len=%zu", 
             report_type, report_id, *data_len);
    
    // Use fixed buffer sizes like working implementation
    uint8_t buffer[64] = {0}; // Fixed size buffer
    size_t expected_len = std::min(*data_len, sizeof(buffer));
    
    // Create USB control transfer for HID GET_REPORT
    const uint8_t bmRequestType = USB_BM_REQUEST_TYPE_DIR_IN | 
                                 USB_BM_REQUEST_TYPE_TYPE_CLASS | 
                                 USB_BM_REQUEST_TYPE_RECIP_INTERFACE;
    const uint8_t bRequest = 0x01; // HID GET_REPORT
    const uint16_t wValue = (report_type << 8) | report_id;
    const uint16_t wIndex = device_.interface_num;
    const uint16_t wLength = expected_len;
    
    usb_transfer_t *transfer = nullptr;
    size_t transfer_size = sizeof(usb_setup_packet_t) + expected_len;
    esp_err_t ret = usb_host_transfer_alloc(transfer_size, 0, &transfer);
    if (ret != ESP_OK) {
        ESP_LOGE(ESP32_USB_TAG, "Failed to allocate transfer: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Setup control transfer
    transfer->device_handle = device_.dev_hdl;
    transfer->bEndpointAddress = 0;
    transfer->num_bytes = transfer_size;
    transfer->timeout_ms = timeout_ms;
    
    // Create setup packet
    usb_setup_packet_t *setup = (usb_setup_packet_t*)transfer->data_buffer;
    setup->bmRequestType = bmRequestType;
    setup->bRequest = bRequest;
    setup->wValue = wValue;
    setup->wIndex = wIndex;
    setup->wLength = wLength;
    
    // Use semaphore for synchronous operation. Heap-allocated (not a stack
    // local) - see the HidTransferCtx comment above for why.
    SemaphoreHandle_t done_sem = xSemaphoreCreateBinary();
    if (!done_sem) {
        usb_host_transfer_free(transfer);
        return ESP_ERR_NO_MEM;
    }

    auto *ctx = new HidTransferCtx{done_sem, ESP_ERR_TIMEOUT, 0};
    transfer->context = ctx;
    transfer->callback = hid_control_transfer_callback;

    ret = usb_host_transfer_submit_control(device_.client_hdl, transfer);
    if (ret == ESP_OK) {
        if (xSemaphoreTake(done_sem, pdMS_TO_TICKS(timeout_ms)) == pdTRUE) {
            // Callback already ran and won't touch ctx/transfer/sem again;
            // safe to read ctx and clean everything up here.
            ret = ctx->result;
            if (ret == ESP_OK && ctx->actual_bytes > sizeof(usb_setup_packet_t)) {
                size_t data_received = ctx->actual_bytes - sizeof(usb_setup_packet_t);
                size_t copy_len = std::min(data_received, *data_len);
                memcpy(data, transfer->data_buffer + sizeof(usb_setup_packet_t), copy_len);
                *data_len = copy_len;

                ESP_LOGD(ESP32_USB_TAG, "HID GET_REPORT success: received %zu bytes", *data_len);
            } else {
                ESP_LOGW(ESP32_USB_TAG, "HID GET_REPORT: No data received");
                *data_len = 0;
                ret = ESP_FAIL;
            }
            vSemaphoreDelete(done_sem);
            usb_host_transfer_free(transfer);
            delete ctx;
        } else {
            // We gave up locally, but the transfer may still be in flight -
            // usb_host_transfer_free() on a not-yet-completed transfer is
            // unsafe. Hand off cleanup to the callback (whenever, if ever,
            // it fires) instead of freeing anything here.
            ESP_LOGW(ESP32_USB_TAG, "HID GET_REPORT timeout");
            ctx->abandoned.store(true);
            ret = ESP_ERR_TIMEOUT;
        }
    } else {
        // Submit failed synchronously - the callback will never run for
        // this transfer, so we must (and safely can) clean up here.
        ESP_LOGW(ESP32_USB_TAG, "Failed to submit HID GET_REPORT: %s", esp_err_to_name(ret));
        vSemaphoreDelete(done_sem);
        usb_host_transfer_free(transfer);
        delete ctx;
    }

    return ret;
}

esp_err_t Esp32UsbTransport::hid_set_report(uint8_t report_type, uint8_t report_id,
                                           const uint8_t* data, size_t data_len,
                                           uint32_t timeout_ms) {
    if (!device_.dev_hdl) {
        ESP_LOGE(ESP32_USB_TAG, "HID SET_REPORT: No device handle");
        return ESP_ERR_INVALID_ARG;
    }
    if (!data || data_len == 0) {
        ESP_LOGE(ESP32_USB_TAG, "HID SET_REPORT: Invalid parameters");
        return ESP_ERR_INVALID_ARG;
    }

    ESP_LOGD(ESP32_USB_TAG, "HID SET_REPORT: type=0x%02X, id=0x%02X, len=%zu", 
             report_type, report_id, data_len);
    
    // Create USB control transfer for HID SET_REPORT
    const uint8_t bmRequestType = USB_BM_REQUEST_TYPE_DIR_OUT | 
                                 USB_BM_REQUEST_TYPE_TYPE_CLASS | 
                                 USB_BM_REQUEST_TYPE_RECIP_INTERFACE;
    const uint8_t bRequest = 0x09; // HID SET_REPORT
    const uint16_t wValue = (report_type << 8) | report_id;
    const uint16_t wIndex = device_.interface_num;
    const uint16_t wLength = data_len;
    
    usb_transfer_t *transfer = nullptr;
    size_t transfer_size = sizeof(usb_setup_packet_t) + data_len;
    esp_err_t ret = usb_host_transfer_alloc(transfer_size, 0, &transfer);
    if (ret != ESP_OK) {
        ESP_LOGE(ESP32_USB_TAG, "Failed to allocate transfer: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Setup control transfer
    transfer->device_handle = device_.dev_hdl;
    transfer->bEndpointAddress = 0;
    transfer->num_bytes = transfer_size;
    transfer->timeout_ms = timeout_ms;
    
    // Create setup packet
    usb_setup_packet_t *setup = (usb_setup_packet_t*)transfer->data_buffer;
    setup->bmRequestType = bmRequestType;
    setup->bRequest = bRequest;
    setup->wValue = wValue;
    setup->wIndex = wIndex;
    setup->wLength = wLength;
    
    // Copy data to transfer buffer
    memcpy(transfer->data_buffer + sizeof(usb_setup_packet_t), data, data_len);
    
    // Use semaphore for synchronous operation. Heap-allocated (not a stack
    // local) - see the HidTransferCtx comment near the top of this file.
    SemaphoreHandle_t done_sem = xSemaphoreCreateBinary();
    if (!done_sem) {
        usb_host_transfer_free(transfer);
        return ESP_ERR_NO_MEM;
    }

    auto *ctx = new HidTransferCtx{done_sem, ESP_ERR_TIMEOUT, 0};
    transfer->context = ctx;
    transfer->callback = hid_control_transfer_callback;

    ret = usb_host_transfer_submit_control(device_.client_hdl, transfer);
    if (ret == ESP_OK) {
        if (xSemaphoreTake(done_sem, pdMS_TO_TICKS(timeout_ms)) == pdTRUE) {
            ret = ctx->result;
            if (ret == ESP_OK) {
                ESP_LOGD(ESP32_USB_TAG, "HID SET_REPORT success");
            } else {
                ESP_LOGW(ESP32_USB_TAG, "HID SET_REPORT failed");
            }
            vSemaphoreDelete(done_sem);
            usb_host_transfer_free(transfer);
            delete ctx;
        } else {
            // See HidTransferCtx comment: transfer may still be in flight,
            // hand cleanup off to the callback instead of freeing here.
            ESP_LOGW(ESP32_USB_TAG, "HID SET_REPORT timeout");
            ctx->abandoned.store(true);
            ret = ESP_ERR_TIMEOUT;
        }
    } else {
        ESP_LOGW(ESP32_USB_TAG, "Failed to submit HID SET_REPORT: %s", esp_err_to_name(ret));
        vSemaphoreDelete(done_sem);
        usb_host_transfer_free(transfer);
        delete ctx;
    }

    return ret;
}

esp_err_t Esp32UsbTransport::hid_interrupt_read(uint8_t* data, size_t* data_len,
                                               uint32_t timeout_ms) {
    if (!device_.dev_hdl) {
        ESP_LOGE(ESP32_USB_TAG, "HID interrupt read: No device handle");
        return ESP_ERR_INVALID_ARG;
    }
    if (!data || !data_len || *data_len == 0) {
        ESP_LOGE(ESP32_USB_TAG, "HID interrupt read: Invalid parameters");
        return ESP_ERR_INVALID_ARG;
    }
    if (device_.ep_in == 0) {
        ESP_LOGE(ESP32_USB_TAG, "HID interrupt read: No IN endpoint available");
        return ESP_ERR_INVALID_STATE;
    }

    size_t expected_len = std::min(*data_len, static_cast<size_t>(device_.max_packet_size_in
                                                                        ? device_.max_packet_size_in
                                                                        : *data_len));

    ESP_LOGD(ESP32_USB_TAG, "HID interrupt read: ep=0x%02X, max_len=%zu", device_.ep_in, expected_len);

    // Plain interrupt IN transfer - no control setup packet, data goes
    // straight into transfer->data_buffer.
    usb_transfer_t *transfer = nullptr;
    esp_err_t ret = usb_host_transfer_alloc(expected_len, 0, &transfer);
    if (ret != ESP_OK) {
        ESP_LOGE(ESP32_USB_TAG, "Failed to allocate interrupt transfer: %s", esp_err_to_name(ret));
        return ret;
    }

    transfer->device_handle = device_.dev_hdl;
    transfer->bEndpointAddress = device_.ep_in;
    transfer->num_bytes = expected_len;
    transfer->timeout_ms = timeout_ms;

    // Use semaphore for synchronous operation. Heap-allocated (not a stack
    // local) - see the HidTransferCtx comment near the top of this file.
    SemaphoreHandle_t done_sem = xSemaphoreCreateBinary();
    if (!done_sem) {
        usb_host_transfer_free(transfer);
        return ESP_ERR_NO_MEM;
    }

    auto *ctx = new HidTransferCtx{done_sem, ESP_ERR_TIMEOUT, 0};
    transfer->context = ctx;
    transfer->callback = hid_control_transfer_callback;

    ret = usb_host_transfer_submit(transfer);
    if (ret == ESP_OK) {
        if (xSemaphoreTake(done_sem, pdMS_TO_TICKS(timeout_ms)) == pdTRUE) {
            ret = ctx->result;
            if (ret == ESP_OK && ctx->actual_bytes > 0) {
                size_t copy_len = std::min(ctx->actual_bytes, *data_len);
                memcpy(data, transfer->data_buffer, copy_len);
                *data_len = copy_len;
                ESP_LOGD(ESP32_USB_TAG, "HID interrupt read success: received %zu bytes", *data_len);
            } else {
                ESP_LOGW(ESP32_USB_TAG, "HID interrupt read: No data received");
                *data_len = 0;
                ret = ESP_FAIL;
            }
            vSemaphoreDelete(done_sem);
            usb_host_transfer_free(transfer);
            delete ctx;
        } else {
            // See HidTransferCtx comment: transfer may still be in flight,
            // hand cleanup off to the callback instead of freeing here.
            ESP_LOGW(ESP32_USB_TAG, "HID interrupt read timeout");
            ctx->abandoned.store(true);
            ret = ESP_ERR_TIMEOUT;
        }
    } else {
        ESP_LOGW(ESP32_USB_TAG, "Failed to submit HID interrupt read: %s", esp_err_to_name(ret));
        vSemaphoreDelete(done_sem);
        usb_host_transfer_free(transfer);
        delete ctx;
    }

    return ret;
}

esp_err_t Esp32UsbTransport::get_string_descriptor(uint8_t string_index,
                                                 std::string& result) {
    result.clear();
    
    if (!device_.dev_hdl) {
        set_last_error("USB device not ready");
        return ESP_ERR_INVALID_STATE;
    }
    
    ESP_LOGD(ESP32_USB_TAG, "USB GET_STRING_DESCRIPTOR: index=%d, language_id=0x0409", string_index);
    
    // USB string descriptors can be up to 255 bytes, but typically much smaller
    const size_t max_string_len = 255;
    const uint16_t language_id = 0x0409; // English US
    
    // USB string descriptor request parameters
    const uint8_t bmRequestType = USB_BM_REQUEST_TYPE_DIR_IN | 
                                 USB_BM_REQUEST_TYPE_TYPE_STANDARD | 
                                 USB_BM_REQUEST_TYPE_RECIP_DEVICE;
    const uint8_t bRequest = USB_B_REQUEST_GET_DESCRIPTOR;
    const uint16_t wValue = (USB_B_DESCRIPTOR_TYPE_STRING << 8) | string_index;
    const uint16_t wIndex = language_id;
    const uint16_t wLength = max_string_len;
    
    usb_transfer_t *transfer = nullptr;
    size_t transfer_size = sizeof(usb_setup_packet_t) + max_string_len;
    esp_err_t ret = usb_host_transfer_alloc(transfer_size, 0, &transfer);
    if (ret != ESP_OK) {
        set_last_error("Failed to allocate string descriptor transfer: " + std::string(esp_err_to_name(ret)));
        return ret;
    }
    
    // Setup control transfer
    transfer->device_handle = device_.dev_hdl;
    transfer->bEndpointAddress = 0; // Control endpoint
    transfer->num_bytes = transfer_size;
    transfer->timeout_ms = timing::USB_CONTROL_TRANSFER_TIMEOUT_MS;
    
    // Create setup packet
    usb_setup_packet_t *setup = (usb_setup_packet_t*)transfer->data_buffer;
    setup->bmRequestType = bmRequestType;
    setup->bRequest = bRequest;
    setup->wValue = wValue;
    setup->wIndex = wIndex;
    setup->wLength = wLength;
    
    // Use semaphore for synchronous operation. Heap-allocated (not a stack
    // local) - see the HidTransferCtx comment near the top of this file.
    SemaphoreHandle_t done_sem = xSemaphoreCreateBinary();
    if (!done_sem) {
        usb_host_transfer_free(transfer);
        return ESP_ERR_NO_MEM;
    }

    auto *ctx = new HidTransferCtx{done_sem, ESP_ERR_TIMEOUT, 0};
    transfer->context = ctx;
    transfer->callback = hid_control_transfer_callback;
    
    ret = usb_host_transfer_submit_control(device_.client_hdl, transfer);
    if (ret == ESP_OK) {
        if (xSemaphoreTake(done_sem, pdMS_TO_TICKS(timing::USB_SEMAPHORE_TIMEOUT_MS)) == pdTRUE) {
            ret = ctx->result;
            if (ret == ESP_OK && ctx->actual_bytes > sizeof(usb_setup_packet_t)) {
                // Parse the USB string descriptor
                uint8_t *desc_data = transfer->data_buffer + sizeof(usb_setup_packet_t);
                size_t desc_len = ctx->actual_bytes - sizeof(usb_setup_packet_t);
                
                if (desc_len >= 2) {
                    uint8_t bLength = desc_data[0];        // Total length of descriptor
                    uint8_t bDescriptorType = desc_data[1]; // Should be USB_B_DESCRIPTOR_TYPE_STRING (0x03)
                    
                    if (bDescriptorType == USB_B_DESCRIPTOR_TYPE_STRING && bLength >= 2) {
                        // USB string descriptors are UTF-16LE encoded, skip the 2-byte header
                        size_t string_data_len = std::min(static_cast<size_t>(bLength - 2), desc_len - 2);
                        uint8_t *string_data = desc_data + 2;
                        
                        // Convert UTF-16LE to ASCII (simplified, handles ASCII characters)
                        result.reserve(string_data_len / 2);
                        for (size_t i = 0; i < string_data_len; i += 2) {
                            if (i + 1 < string_data_len) {
                                uint16_t utf16_char = string_data[i] | (string_data[i + 1] << 8);
                                if (utf16_char < 128 && utf16_char > 0) { // ASCII range, non-null
                                    result += static_cast<char>(utf16_char);
                                } else if (utf16_char >= 128) {
                                    result += '?'; // Non-ASCII character placeholder
                                }
                            }
                        }
                        
                        // Trim trailing whitespace
                        while (!result.empty() && std::isspace(result.back())) {
                            result.pop_back();
                        }
                        
                        ESP_LOGI(ESP32_USB_TAG, "USB string descriptor %d: \"%s\"", string_index, result.c_str());
                    } else {
                        ESP_LOGW(ESP32_USB_TAG, "Invalid string descriptor: type=0x%02X, length=%d", bDescriptorType, bLength);
                        ret = ESP_ERR_INVALID_RESPONSE;
                    }
                } else {
                    ESP_LOGW(ESP32_USB_TAG, "String descriptor too short: %zu bytes", desc_len);
                    ret = ESP_ERR_INVALID_SIZE;
                }
            } else {
                ESP_LOGW(ESP32_USB_TAG, "USB string descriptor request failed or no data received");
                ret = ESP_FAIL;
            }
            vSemaphoreDelete(done_sem);
            usb_host_transfer_free(transfer);
            delete ctx;
        } else {
            // See HidTransferCtx comment: transfer may still be in flight,
            // hand cleanup off to the callback instead of freeing here.
            ESP_LOGW(ESP32_USB_TAG, "USB string descriptor request timeout");
            ctx->abandoned.store(true);
            ret = ESP_ERR_TIMEOUT;
        }
    } else {
        ESP_LOGW(ESP32_USB_TAG, "Failed to submit string descriptor request: %s", esp_err_to_name(ret));
        vSemaphoreDelete(done_sem);
        usb_host_transfer_free(transfer);
        delete ctx;
    }
    
    return ret;
}

std::string Esp32UsbTransport::get_last_error() const {
    std::lock_guard<std::mutex> lock(error_mutex_);
    return last_error_;
}

// Private methods implementation

void Esp32UsbTransport::set_last_error(const std::string& error) {
    std::lock_guard<std::mutex> lock(error_mutex_);
    last_error_ = error;
    ESP_LOGW(ESP32_USB_TAG, "%s", error.c_str());
}

esp_err_t Esp32UsbTransport::setup_usb_host() {
    // Create USB library task - USB Host installation happens inside the task
    if (!usb_tasks_running_.load()) {
        usb_tasks_running_ = true;
        
        // Create USB Host Library task first
        BaseType_t task_created = xTaskCreate(usb_lib_task, "usb_lib_task", 4096, this, 2, &usb_lib_task_handle_);
        if (task_created != pdTRUE) {
            ESP_LOGE(ESP32_USB_TAG, "Failed to create USB Host Library task");
            usb_tasks_running_ = false;
            return ESP_FAIL;
        }
        
        // Give USB Host Library task time to initialize
        vTaskDelay(pdMS_TO_TICKS(100));
        
        // Create USB client task
        task_created = xTaskCreate(usb_client_task, "usb_client_task", 6144, this, 3, &usb_client_task_handle_);
        if (task_created != pdTRUE) {
            ESP_LOGE(ESP32_USB_TAG, "Failed to create USB client task");
            usb_tasks_running_ = false;
            return ESP_FAIL;
        }
        
        ESP_LOGI(ESP32_USB_TAG, "USB Host tasks created successfully");
    }
    
    return ESP_OK;
}

esp_err_t Esp32UsbTransport::teardown_usb_host() {
    // Signal tasks to stop (they will self-terminate and handle USB cleanup)
    if (usb_tasks_running_.load()) {
        ESP_LOGI(ESP32_USB_TAG, "Stopping USB Host tasks...");
        usb_tasks_running_ = false;
        
        // Wait for tasks to self-terminate
        vTaskDelay(pdMS_TO_TICKS(500)); // Give tasks time to exit cleanly
        
        usb_client_task_handle_ = nullptr;
        usb_lib_task_handle_ = nullptr;
        
        ESP_LOGI(ESP32_USB_TAG, "USB Host tasks stopped");
    }
    
    // Release interface and device
    if (device_.dev_hdl) {
        ESP_LOGI(ESP32_USB_TAG, "Cleaning up device resources");
        usb_host_interface_release(device_.client_hdl, device_.dev_hdl, device_.interface_num);
        usb_host_device_close(device_.client_hdl, device_.dev_hdl);
        device_.dev_hdl = nullptr;
    }
    
    if (device_.client_hdl) {
        ESP_LOGI(ESP32_USB_TAG, "Deregistering USB client");
        usb_host_client_deregister(device_.client_hdl);
        device_.client_hdl = nullptr;
    }
    
    // USB Host uninstallation happens inside usb_lib_task now
    return ESP_OK;
}

esp_err_t Esp32UsbTransport::find_and_open_device() {
    // Register USB client in asynchronous mode for event-driven device detection
    usb_host_client_config_t client_config = {
        .is_synchronous = false,  // Use asynchronous mode for USB_HOST_CLIENT_EVENT_NEW_DEV events
        .max_num_event_msg = 5,
        .async = {
            .client_event_callback = usb_client_event_callback,
            .callback_arg = this
        }
    };
    
    esp_err_t ret = usb_host_client_register(&client_config, &device_.client_hdl);
    if (ret != ESP_OK) {
        set_last_error("Client register failed: " + std::string(esp_err_to_name(ret)));
        return ret;
    }
    
    ESP_LOGI(ESP32_USB_TAG, "USB client registered (handle=0x%p), waiting for device connection events...", 
             device_.client_hdl);
    
    // Force immediate device enumeration check in addition to event-driven detection
    ESP_LOGI(ESP32_USB_TAG, "Performing immediate device enumeration check...");
    vTaskDelay(pdMS_TO_TICKS(100)); // Small delay for USB stack to stabilize
    
    int num_dev = 10;
    uint8_t dev_addr_list[10];
    esp_err_t enum_ret = usb_host_device_addr_list_fill(num_dev, dev_addr_list, &num_dev);
    if (enum_ret == ESP_OK && num_dev > 0) {
        ESP_LOGI(ESP32_USB_TAG, "Found %d existing USB devices during initial enumeration:", num_dev);
        for (int i = 0; i < num_dev; i++) {
            ESP_LOGI(ESP32_USB_TAG, "  Attempting to handle existing device at address %d", dev_addr_list[i]);
            handle_new_device(dev_addr_list[i]);
        }
    } else {
        ESP_LOGI(ESP32_USB_TAG, "No existing USB devices found - waiting for connection events");
    }
    
    return ESP_OK;
}

esp_err_t Esp32UsbTransport::claim_interface() {
    const usb_config_desc_t *config_desc;
    esp_err_t ret = usb_host_get_active_config_descriptor(device_.dev_hdl, &config_desc);
    if (ret != ESP_OK) {
        set_last_error("Failed to get config descriptor");
        return ret;
    }
    
    // Find HID interface
    const usb_intf_desc_t *intf_desc = nullptr;
    int offset = 0;
    
    for (int i = 0; i < config_desc->bNumInterfaces; i++) {
        intf_desc = usb_parse_interface_descriptor(config_desc, i, 0, &offset);
        if (intf_desc && intf_desc->bInterfaceClass == USB_CLASS_HID) {
            device_.interface_num = intf_desc->bInterfaceNumber;
            break;
        }
    }
    
    if (!intf_desc || intf_desc->bInterfaceClass != USB_CLASS_HID) {
        set_last_error("No HID interface found");
        return ESP_ERR_NOT_FOUND;
    }
    
    ret = usb_host_interface_claim(device_.client_hdl, device_.dev_hdl, 
                                  device_.interface_num, 0);
    if (ret != ESP_OK) {
        set_last_error("Failed to claim interface: " + std::string(esp_err_to_name(ret)));
        return ret;
    }
    
    return ESP_OK;
}

esp_err_t Esp32UsbTransport::find_endpoints() {
    const usb_config_desc_t *config_desc;
    esp_err_t ret = usb_host_get_active_config_descriptor(device_.dev_hdl, &config_desc);
    if (ret != ESP_OK) {
        return ret;
    }
    
    int offset = 0;
    const usb_intf_desc_t *intf_desc = usb_parse_interface_descriptor(
        config_desc, device_.interface_num, 0, &offset);
    
    if (!intf_desc) {
        set_last_error("Interface descriptor not found");
        return ESP_ERR_NOT_FOUND;
    }
    
    // Parse endpoints correctly using ESP-IDF approach
    const usb_ep_desc_t *ep_desc = nullptr;
    int ep_offset = offset;
    
    ESP_LOGD(ESP32_USB_TAG, "Interface has %d endpoints", intf_desc->bNumEndpoints);
    
    for (int i = 0; i < intf_desc->bNumEndpoints; i++) {
        ep_desc = usb_parse_endpoint_descriptor_by_index(intf_desc, i, config_desc->wTotalLength, &ep_offset);
        if (ep_desc) {
            if (USB_EP_DESC_GET_EP_DIR(ep_desc)) {
                // IN endpoint (device to host)
                device_.ep_in = ep_desc->bEndpointAddress;
                device_.max_packet_size_in = ep_desc->wMaxPacketSize;
                ESP_LOGD(ESP32_USB_TAG, "Found IN endpoint: 0x%02X (max packet size: %d)",
                         device_.ep_in, device_.max_packet_size_in);
            } else {
                // OUT endpoint (host to device)
                device_.ep_out = ep_desc->bEndpointAddress;
                device_.max_packet_size_out = ep_desc->wMaxPacketSize;
                ESP_LOGD(ESP32_USB_TAG, "Found OUT endpoint: 0x%02X (max packet size: %d)",
                         device_.ep_out, device_.max_packet_size_out);
            }
        } else {
            ESP_LOGW(ESP32_USB_TAG, "Failed to parse endpoint %d", i);
        }
    }

    if (device_.ep_in == 0) {
        set_last_error("No IN endpoint found");
        return ESP_ERR_NOT_FOUND;
    }

    // Detect input-only devices (no OUT endpoint)
    if (device_.ep_out == 0) {
        ESP_LOGW(ESP32_USB_TAG, "INPUT-ONLY HID device detected - no OUT endpoint available");
        ESP_LOGI(ESP32_USB_TAG, "Device supports HID GET_REPORT only (no SET_REPORT)");
    } else {
        ESP_LOGD(ESP32_USB_TAG, "Bidirectional device detected - has both IN and OUT endpoints");
    }
    
    return ESP_OK;
}

esp_err_t Esp32UsbTransport::submit_control_transfer(uint8_t bmRequestType, uint8_t bRequest,
                                                   uint16_t wValue, uint16_t wIndex,
                                                   uint8_t* data, size_t data_len,
                                                   uint32_t timeout_ms) {
    std::lock_guard<std::mutex> lock(device_mutex_);
    
    if (!device_.dev_hdl) {
        return ESP_ERR_INVALID_STATE;
    }
    
    usb_transfer_t *transfer;
    esp_err_t ret = usb_host_transfer_alloc(sizeof(usb_setup_packet_t) + data_len, 0, &transfer);
    if (ret != ESP_OK) {
        set_last_error("Transfer alloc failed: " + std::string(esp_err_to_name(ret)));
        return ret;
    }
    
    // Setup packet
    usb_setup_packet_t *setup = (usb_setup_packet_t *)transfer->data_buffer;
    setup->bmRequestType = bmRequestType;
    setup->bRequest = bRequest;
    setup->wValue = wValue;
    setup->wIndex = wIndex;
    setup->wLength = data_len;
    
    if (data_len > 0 && data) {
        if (bmRequestType & USB_BM_REQUEST_TYPE_DIR_IN) {
            // IN transfer - device to host
            memset(transfer->data_buffer + sizeof(usb_setup_packet_t), 0, data_len);
        } else {
            // OUT transfer - host to device
            memcpy(transfer->data_buffer + sizeof(usb_setup_packet_t), data, data_len);
        }
    }
    
    transfer->device_handle = device_.dev_hdl;
    transfer->bEndpointAddress = 0; // Control endpoint
    transfer->callback = nullptr;
    transfer->context = nullptr;
    transfer->num_bytes = sizeof(usb_setup_packet_t) + data_len;
    transfer->timeout_ms = timeout_ms;
    
    ret = usb_host_transfer_submit_control(device_.client_hdl, transfer);
    if (ret != ESP_OK) {
        usb_host_transfer_free(transfer);
        set_last_error("Control transfer submit failed: " + std::string(esp_err_to_name(ret)));
        return ret;
    }
    
    // Copy response data back
    if (data_len > 0 && data && (bmRequestType & USB_BM_REQUEST_TYPE_DIR_IN)) {
        memcpy(data, transfer->data_buffer + sizeof(usb_setup_packet_t), data_len);
    }
    
    usb_host_transfer_free(transfer);
    return ESP_OK;
}

void Esp32UsbTransport::usb_client_event_callback(const usb_host_client_event_msg_t* event_msg, void* arg) {
    Esp32UsbTransport* transport = static_cast<Esp32UsbTransport*>(arg);
    
    switch (event_msg->event) {
        case USB_HOST_CLIENT_EVENT_NEW_DEV:
            ESP_LOGI(ESP32_USB_TAG, "New USB device detected: address=%d", event_msg->new_dev.address);
            transport->handle_new_device(event_msg->new_dev.address);
            break;
            
        case USB_HOST_CLIENT_EVENT_DEV_GONE:
            ESP_LOGI(ESP32_USB_TAG, "USB device disconnected");
            transport->handle_device_gone(event_msg->dev_gone.dev_hdl);
            break;
            
        default:
            ESP_LOGW(ESP32_USB_TAG, "Unhandled USB client event: %d", event_msg->event);
            break;
    }
}

void Esp32UsbTransport::handle_new_device(uint8_t dev_addr) {
    ESP_LOGI(ESP32_USB_TAG, "Handling new USB device at address %d", dev_addr);
    
    std::lock_guard<std::mutex> lock(device_mutex_);
    
    // Check if we already have a device connected
    if (device_.dev_hdl != nullptr) {
        ESP_LOGW(ESP32_USB_TAG, "Device already connected - skipping new device at address %d", dev_addr);
        return;
    }
    
    // Open the device
    esp_err_t ret = usb_host_device_open(device_.client_hdl, dev_addr, &device_.dev_hdl);
    if (ret != ESP_OK) {
        ESP_LOGE(ESP32_USB_TAG, "Failed to open device at address %d: %s", dev_addr, esp_err_to_name(ret));
        return;
    }
    
    ESP_LOGI(ESP32_USB_TAG, "Successfully opened USB device at address %d", dev_addr);
    
    // Get device information
    usb_device_info_t dev_info;
    ret = usb_host_device_info(device_.dev_hdl, &dev_info);
    if (ret != ESP_OK) {
        ESP_LOGE(ESP32_USB_TAG, "Failed to get device info: %s", esp_err_to_name(ret));
        usb_host_device_close(device_.client_hdl, device_.dev_hdl);
        device_.dev_hdl = nullptr;
        return;
    }
    
    device_.address = dev_addr;
    device_.speed = dev_info.speed;
    
    // Get device descriptor to extract VID/PID
    const usb_device_desc_t* device_desc;
    ret = usb_host_get_device_descriptor(device_.dev_hdl, &device_desc);
    if (ret == ESP_OK) {
        device_.vendor_id = device_desc->idVendor;
        device_.product_id = device_desc->idProduct;
        
        ESP_LOGI(ESP32_USB_TAG, "USB device opened: VID=0x%04X, PID=0x%04X, Speed=%d", 
                 device_.vendor_id, device_.product_id, dev_info.speed);
        
        // Check if this is a UPS device (HID class)
        if (device_desc->bDeviceClass == USB_CLASS_HID || 
            device_desc->bDeviceClass == 0x00) { // Device class defined at interface level
            
            // Try to claim HID interface and find endpoints
            ret = claim_interface();
            if (ret == ESP_OK) {
                ret = find_endpoints();
                if (ret == ESP_OK) {
                    connected_ = true;
                    ESP_LOGI(ESP32_USB_TAG, "UPS device successfully configured and ready");
                    return;
                }
            }
        } else {
            ESP_LOGW(ESP32_USB_TAG, "Connected device is not a HID device (class=0x%02X)", device_desc->bDeviceClass);
        }
    }
    
    // Clean up on failure
    usb_host_device_close(device_.client_hdl, device_.dev_hdl);
    device_.dev_hdl = nullptr;
}

void Esp32UsbTransport::handle_device_gone(usb_device_handle_t dev_hdl) {
    ESP_LOGI(ESP32_USB_TAG, "Handling USB device disconnection");
    
    std::lock_guard<std::mutex> lock(device_mutex_);
    
    if (device_.dev_hdl == dev_hdl) {
        connected_ = false;
        
        // Clean up device resources
        if (device_.dev_hdl) {
            usb_host_interface_release(device_.client_hdl, device_.dev_hdl, device_.interface_num);
            usb_host_device_close(device_.client_hdl, device_.dev_hdl);
            device_.dev_hdl = nullptr;
        }
        
        // Reset device info
        device_.address = 0;
        device_.vendor_id = 0;
        device_.product_id = 0;
        
        ESP_LOGI(ESP32_USB_TAG, "USB device disconnected and cleaned up");
    }
}

void Esp32UsbTransport::usb_lib_task(void* arg) {
    Esp32UsbTransport* transport = static_cast<Esp32UsbTransport*>(arg);
    
    ESP_LOGI(ESP32_USB_TAG, "USB Host Library task starting...");
    
    // Initialize USB Host library inside task (following working prototype)
    usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1
    };

    esp_err_t ret = usb_host_install(&host_config);
    if (ret != ESP_OK) {
        ESP_LOGE(ESP32_USB_TAG, "USB Host install failed: %s", esp_err_to_name(ret));
        transport->usb_tasks_running_ = false; // Stop other tasks
        vTaskDelete(nullptr);
        return;
    }

    ESP_LOGI(ESP32_USB_TAG, "USB Host library installed successfully");
    
    // Main USB Host event loop - following working prototype pattern
    bool has_clients = true;
    bool has_devices = false;
    
    while (has_clients && transport->usb_tasks_running_.load()) {
        uint32_t event_flags;
        ret = usb_host_lib_handle_events(portMAX_DELAY, &event_flags);
        
        if (ret != ESP_OK) {
            ESP_LOGE(ESP32_USB_TAG, "USB Host event handling failed: %s", esp_err_to_name(ret));
            continue;
        }

        // Handle USB Host events (following ESP-IDF v5.4 patterns)
        if (event_flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
            ESP_LOGI(ESP32_USB_TAG, "No more USB clients");
            if (usb_host_device_free_all() == ESP_OK) {
                ESP_LOGI(ESP32_USB_TAG, "All devices freed");
                has_clients = false;
            } else {
                ESP_LOGI(ESP32_USB_TAG, "Waiting for devices to be freed");
                has_devices = true;
            }
        }
        
        if (has_devices && (event_flags & USB_HOST_LIB_EVENT_FLAGS_ALL_FREE)) {
            ESP_LOGI(ESP32_USB_TAG, "All devices freed");
            has_clients = false;
        }
    }
    
    // Cleanup USB Host library
    ESP_LOGI(ESP32_USB_TAG, "Uninstalling USB Host library");
    usb_host_uninstall();
    
    ESP_LOGI(ESP32_USB_TAG, "USB Host Library task ending");
    vTaskDelete(nullptr);
}

void Esp32UsbTransport::usb_client_task(void* arg) {
    Esp32UsbTransport* transport = static_cast<Esp32UsbTransport*>(arg);
    
    ESP_LOGI(ESP32_USB_TAG, "USB client task started");
    
    while (transport->usb_tasks_running_.load()) {
        if (transport->device_.client_hdl) {
            // Use shorter timeout for more responsive event processing
            esp_err_t ret = usb_host_client_handle_events(transport->device_.client_hdl, timing::USB_CLIENT_EVENT_TIMEOUT_MS);
            
            if (ret == ESP_ERR_TIMEOUT) {
                // Timeout is normal - continue processing
            } else if (ret != ESP_OK) {
                ESP_LOGW(ESP32_USB_TAG, "USB client event handling failed: %s", esp_err_to_name(ret));
                vTaskDelay(pdMS_TO_TICKS(100)); // Brief delay on error
            }
        } else {
            ESP_LOGD(ESP32_USB_TAG, "No USB client handle available");
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        
        // Small delay to prevent busy-waiting
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    
    ESP_LOGI(ESP32_USB_TAG, "USB client task stopping");
    vTaskDelete(nullptr);
}

} // namespace ups_hid
} // namespace esphome

#endif // USE_ESP32