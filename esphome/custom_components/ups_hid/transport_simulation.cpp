#include "transport_simulation.h"
#include "esphome/core/log.h"
#include <cstring>
#include <cmath>

namespace esphome {
namespace ups_hid {

static const char *const SIM_TRANSPORT_TAG = "ups_hid.simulation";

SimulatedTransport::SimulatedTransport() {
    start_time_ = std::chrono::steady_clock::now();
}

esp_err_t SimulatedTransport::initialize() {
    if (initialized_) {
        return ESP_OK;
    }
    
    ESP_LOGI(SIM_TRANSPORT_TAG, "Initializing simulated USB transport");
    ESP_LOGI(SIM_TRANSPORT_TAG, "Simulating APC Back-UPS ES (VID=0x051D, PID=0x0002)");
    
    initialized_ = true;
    connected_ = true;
    
    return ESP_OK;
}

esp_err_t SimulatedTransport::deinitialize() {
    if (!initialized_) {
        return ESP_OK;
    }
    
    ESP_LOGI(SIM_TRANSPORT_TAG, "Deinitializing simulated USB transport");
    
    initialized_ = false;
    connected_ = false;
    
    return ESP_OK;
}

bool SimulatedTransport::is_connected() const {
    return connected_ && initialized_;
}

uint16_t SimulatedTransport::get_vendor_id() const {
    return vendor_id_;
}

uint16_t SimulatedTransport::get_product_id() const {
    return product_id_;
}

esp_err_t SimulatedTransport::hid_get_report(uint8_t report_type, uint8_t report_id, 
                                           uint8_t* data, size_t* data_len, 
                                           uint32_t timeout_ms) {
    if (!is_connected()) {
        last_error_ = "Simulated transport not connected";
        return ESP_ERR_INVALID_STATE;
    }
    
    // Update dynamic simulation data
    update_simulation_data();
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Simulating HID GET_REPORT: type=0x%02X, id=0x%02X", 
             report_type, report_id);
    
    // Clear the buffer first
    memset(data, 0, *data_len);
    data[0] = report_id; // First byte is always report ID
    
    // Generate simulated data based on report ID
    switch (report_id) {
        case 0x01: // Status report
            generate_status_report(report_id, data, data_len);
            break;
            
        case 0x06: // Battery report
            generate_battery_report(report_id, data, data_len);
            break;
            
        case 0x07: // Load report
            generate_power_report(report_id, data, data_len);
            break;
            
        case 0x0C: // Power summary
            generate_battery_report(report_id, data, data_len);
            break;
            
        case 0x0E: // Voltage report
            generate_power_report(report_id, data, data_len);
            break;
            
        case 0x1F: // Beeper control
        case 0x18: // Audible alarm
            generate_beeper_report(report_id, data, data_len);
            break;
            
        case 0x03: // Device info
        case 0x04: // Firmware
            generate_device_info_report(report_id, data, data_len);
            break;
            
        case 0x35: // Sensitivity
            *data_len = 2;
            data[1] = 1; // Normal sensitivity
            break;
            
        default:
            // Return zeros for unknown reports
            *data_len = 6; // Standard HID report size
            ESP_LOGV(SIM_TRANSPORT_TAG, "Unknown report ID 0x%02X, returning zeros", report_id);
            break;
    }
    
    return ESP_OK;
}

esp_err_t SimulatedTransport::hid_set_report(uint8_t report_type, uint8_t report_id,
                                           const uint8_t* data, size_t data_len,
                                           uint32_t timeout_ms) {
    if (!is_connected()) {
        last_error_ = "Simulated transport not connected";
        return ESP_ERR_INVALID_STATE;
    }
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Simulating HID SET_REPORT: type=0x%02X, id=0x%02X, len=%zu", 
             report_type, report_id, data_len);
    
    // Simulate beeper control
    if (report_id == 0x1F || report_id == 0x18) {
        if (data_len >= 2) {
            uint8_t beeper_value = data[1];
            switch (beeper_value) {
                case 1:
                    beeper_status_ = "disabled";
                    ESP_LOGI(SIM_TRANSPORT_TAG, "Simulated beeper disabled");
                    break;
                case 2:
                    beeper_status_ = "enabled";
                    ESP_LOGI(SIM_TRANSPORT_TAG, "Simulated beeper enabled");
                    break;
                case 3:
                    beeper_status_ = "muted";
                    ESP_LOGI(SIM_TRANSPORT_TAG, "Simulated beeper muted");
                    break;
                case 4:
                    beeper_status_ = "test";
                    ESP_LOGI(SIM_TRANSPORT_TAG, "Simulated beeper test");
                    break;
                default:
                    ESP_LOGW(SIM_TRANSPORT_TAG, "Unknown beeper command: %d", beeper_value);
                    break;
            }
        }
    }
    
    // Simulate test commands
    if (report_id == 0x20 || report_id == 0x21) { // Battery test commands
        if (data_len >= 2) {
            uint8_t test_cmd = data[1];
            if (test_cmd == 1) {
                test_running_ = true;
                test_result_ = "Battery test in progress";
                ESP_LOGI(SIM_TRANSPORT_TAG, "Simulated battery test started");
            } else if (test_cmd == 0) {
                test_running_ = false;
                test_result_ = "Battery test completed - Good";
                ESP_LOGI(SIM_TRANSPORT_TAG, "Simulated battery test stopped");
            }
        }
    }
    
    return ESP_OK;
}

esp_err_t SimulatedTransport::hid_interrupt_read(uint8_t* data, size_t* data_len,
                                                uint32_t timeout_ms) {
    // The simulated transport models a standard HID Power Device (like the
    // default-simulated APC unit above) - it doesn't have an interrupt-pipe
    // Megatec/Q1 device to simulate. Real hardware only calls this from
    // MegatecProtocol, which isn't exercised in simulation mode.
    (void) timeout_ms;
    ESP_LOGV(SIM_TRANSPORT_TAG, "hid_interrupt_read() not simulated");
    if (data_len) *data_len = 0;
    (void) data;
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t SimulatedTransport::get_string_descriptor(uint8_t string_index, 
                                                  std::string& result) {
    if (!is_connected()) {
        last_error_ = "Simulated transport not connected";
        return ESP_ERR_INVALID_STATE;
    }
    
    // Simulate string descriptors
    switch (string_index) {
        case 1: // Manufacturer
            result = "American Power Conversion";
            break;
        case 2: // Product
            result = "Back-UPS ES 700 FW:866.L4.I USB FW:L4";
            break;
        case 3: // Serial number
            result = "4B2037P30628";
            break;
        case 4: // Firmware (custom)
            result = "866.L4.I";
            break;
        default:
            result = "Unknown";
            ESP_LOGW(SIM_TRANSPORT_TAG, "Unknown string index: %d", string_index);
            return ESP_ERR_NOT_FOUND;
    }
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Simulated string descriptor %d: '%s'", 
             string_index, result.c_str());
    return ESP_OK;
}

std::string SimulatedTransport::get_last_error() const {
    return last_error_;
}

// Private methods

void SimulatedTransport::update_simulation_data() {
    float elapsed = get_elapsed_seconds();
    
    // Simulate battery level slowly decreasing when on battery
    if (input_voltage_ < 100.0f) { // On battery
        battery_level_ = std::max(10.0f, 95.0f - (elapsed * 0.5f)); // Decrease over time
        runtime_minutes_ = static_cast<uint16_t>(battery_level_ * 0.6f); // Runtime based on battery
    } else {
        // On mains - slowly charge if below 100%
        if (battery_level_ < 100.0f) {
            battery_level_ = std::min(100.0f, battery_level_ + (elapsed * 0.1f));
        }
        runtime_minutes_ = static_cast<uint16_t>(battery_level_ * 0.8f);
    }
    
    // Simulate periodic power fluctuations
    input_voltage_ = 120.0f + sin(elapsed * 0.1f) * 2.0f; // Slight voltage variation
    output_voltage_ = 120.0f + sin(elapsed * 0.05f) * 1.0f;
    
    // Simulate load variations
    load_percent_ = 25.0f + sin(elapsed * 0.2f) * 5.0f; // 20-30% load
    
    // Simulate brief battery switch every 5 minutes for testing
    if (fmod(elapsed, 300.0f) < 30.0f) { // 30 seconds on battery every 5 minutes
        input_voltage_ = 0.0f; // Simulate power outage
    }
}

float SimulatedTransport::get_elapsed_seconds() const {
    auto now = std::chrono::steady_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(now - start_time_);
    return static_cast<float>(duration.count());
}

void SimulatedTransport::generate_battery_report(uint8_t report_id, uint8_t* data, size_t* data_len) {
    *data_len = 6;
    
    if (report_id == 0x06) {
        // Battery status report: [06 level runtime_low runtime_high 00 00]
        data[1] = static_cast<uint8_t>(battery_level_);
        data[2] = runtime_minutes_ & 0xFF;
        data[3] = (runtime_minutes_ >> 8) & 0xFF;
        data[4] = 0x00;
        data[5] = 0x00;
    } else if (report_id == 0x0C) {
        // Power summary: [0C level runtime_low runtime_high]
        data[1] = static_cast<uint8_t>(battery_level_);
        data[2] = runtime_minutes_ & 0xFF;
        data[3] = (runtime_minutes_ >> 8) & 0xFF;
    }
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Generated battery report 0x%02X: level=%.0f%%, runtime=%d min", 
             report_id, battery_level_, runtime_minutes_);
}

void SimulatedTransport::generate_power_report(uint8_t report_id, uint8_t* data, size_t* data_len) {
    *data_len = 6;
    
    if (report_id == 0x07) {
        // Load report: [07 load 00 00 00 00]
        data[1] = static_cast<uint8_t>(load_percent_);
        data[2] = 0x00;
        data[3] = 0x00;
        data[4] = 0x00;
        data[5] = 0x00;
    } else if (report_id == 0x0E) {
        // Voltage report: [0E voltage_low voltage_high 00 00 00]
        uint16_t voltage = static_cast<uint16_t>(input_voltage_);
        data[1] = voltage & 0xFF;
        data[2] = (voltage >> 8) & 0xFF;
        data[3] = 0x00;
        data[4] = 0x00;
        data[5] = 0x00;
    }
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Generated power report 0x%02X: load=%.0f%%, voltage=%.1fV", 
             report_id, load_percent_, input_voltage_);
}

void SimulatedTransport::generate_status_report(uint8_t report_id, uint8_t* data, size_t* data_len) {
    *data_len = 6;
    
    // Status bitmap: online, on_battery, low_battery, etc.
    uint8_t status = 0x00;
    if (input_voltage_ > 100.0f) {
        status |= 0x01; // Online
    } else {
        status |= 0x02; // On battery
    }
    
    if (battery_level_ < 20.0f) {
        status |= 0x04; // Low battery
    }
    
    if (load_percent_ > 80.0f) {
        status |= 0x08; // Overload
    }
    
    data[1] = status;
    data[2] = 0x00;
    data[3] = 0x00;
    data[4] = 0x00;
    data[5] = 0x00;
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Generated status report: 0x%02X", status);
}

void SimulatedTransport::generate_beeper_report(uint8_t report_id, uint8_t* data, size_t* data_len) {
    *data_len = 2;
    
    // Beeper status: 1=disabled, 2=enabled, 3=muted
    if (beeper_status_ == "disabled") {
        data[1] = 1;
    } else if (beeper_status_ == "enabled") {
        data[1] = 2;
    } else if (beeper_status_ == "muted") {
        data[1] = 3;
    } else {
        data[1] = 2; // Default enabled
    }
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Generated beeper report: status=%s (value=%d)", 
             beeper_status_.c_str(), data[1]);
}

void SimulatedTransport::generate_test_report(uint8_t report_id, uint8_t* data, size_t* data_len) {
    *data_len = 6;
    
    if (test_running_) {
        data[1] = 0x01; // Test in progress
        data[2] = 0x50; // 80% progress (example)
    } else {
        data[1] = 0x00; // No test
        data[2] = 0x00;
    }
    
    data[3] = 0x00;
    data[4] = 0x00;
    data[5] = 0x00;
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Generated test report: running=%s", 
             test_running_ ? "true" : "false");
}

void SimulatedTransport::generate_device_info_report(uint8_t report_id, uint8_t* data, size_t* data_len) {
    *data_len = 6;
    
    if (report_id == 0x03) {
        // Device info - simulate some device characteristics
        data[1] = 0x86; // Major version
        data[2] = 0x6C; // Minor version  
        data[3] = 0x04; // Revision
        data[4] = 0x00;
        data[5] = 0x00;
    } else if (report_id == 0x04) {
        // Firmware version
        data[1] = 0x08; // 866 (hex)
        data[2] = 0x66;
        data[3] = 0x4C; // L4 (hex)
        data[4] = 0x34;
        data[5] = 0x00;
    }
    
    ESP_LOGV(SIM_TRANSPORT_TAG, "Generated device info report 0x%02X", report_id);
}

} // namespace ups_hid
} // namespace esphome