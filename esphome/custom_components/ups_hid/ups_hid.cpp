#include "ups_hid.h"
#include "constants_ups.h"
#include "transport_factory.h"
#include "transport_simulation.h"
#ifdef USE_ESP32
#include "transport_esp32.h"
#endif
#include "protocol_factory.h"
#include "protocol_apc.h"
#include "protocol_cyberpower.h"
 
#include "protocol_generic.h"
#include "protocol_megatec.h"
#include "esphome/core/log.h"
#include "esphome/core/application.h"
#include <functional>
#include <cmath>

namespace esphome {
namespace ups_hid {

void UpsHidComponent::setup() {
  ESP_LOGCONFIG(TAG, log_messages::SETTING_UP);

  // Keep the generic HID fallback protocol linked in (see protocol_generic.h).
  // Without this, --gc-sections drops protocol_generic.cpp entirely and no
  // fallback protocol is ever registered for unknown UPS vendors.
  ensure_generic_protocol_linked();

  // Same reasoning for the Megatec/Q1 (Cypress) protocol - see protocol_megatec.h.
  ensure_megatec_protocol_linked();

  // Registration itself (the static constructors triggered by the
  // REGISTER_UPS_*_PROTOCOL macros above) intentionally does no logging -
  // see the comments in protocol_factory.cpp. Log what actually landed in
  // the registries here instead, now that it's safe to do so.
  {
    auto all_protocols = ProtocolFactory::get_all_protocols();
    ESP_LOGCONFIG(TAG, "  Registered UPS protocols: %zu", all_protocols.size());
    for (const auto &vendor_and_info : all_protocols) {
      uint16_t vendor_id = vendor_and_info.first;
      const auto &info = vendor_and_info.second;
      if (vendor_id == 0x0000) {
        ESP_LOGCONFIG(TAG, "    - %s (fallback, priority %d)", info.name.c_str(), info.priority);
      } else {
        ESP_LOGCONFIG(TAG, "    - %s (vendor 0x%04X, priority %d)", info.name.c_str(), vendor_id, info.priority);
      }
    }
  }

  if (!initialize_transport()) {
    ESP_LOGE(TAG, log_messages::TRANSPORT_INIT_FAILED);
    mark_failed();
    return;
  }
  
  // Protocol detection is deferred to update() method to handle asynchronous USB enumeration
  ESP_LOGCONFIG(TAG, log_messages::SETUP_COMPLETE);
}

void UpsHidComponent::update() {
  if (!transport_ || !transport_->is_connected()) {
    // Device not connected yet - normal during startup or after disconnection
    ESP_LOGD(TAG, log_messages::WAITING_FOR_DEVICE);
    return;
  }
  
  // Check if protocol detection is needed
  if (!active_protocol_) {
    ESP_LOGI(TAG, log_messages::ATTEMPTING_DETECTION);
    if (detect_protocol()) {
      ESP_LOGI(TAG, log_messages::PROTOCOL_DETECTED);
      consecutive_failures_ = 0;
    } else {
      consecutive_failures_++;
      ESP_LOGW(TAG, log_messages::DETECTION_FAILED, static_cast<unsigned int>(consecutive_failures_));
      
      if (consecutive_failures_ > max_consecutive_failures_) {
        ESP_LOGE(TAG, log_messages::TOO_MANY_FAILURES);
        mark_failed();
      }
      return;
    }
  }
  
  // Normal data reading with active protocol
  if (read_ups_data()) {
    update_sensors();
    consecutive_failures_ = 0;
    last_successful_read_ = millis();
    
    // Check for timer updates (fast polling during countdowns)
    check_and_update_timers();
  } else {
    consecutive_failures_++;
    ESP_LOGW(TAG, log_messages::READ_FAILED, static_cast<unsigned int>(consecutive_failures_));
    
    if (consecutive_failures_ > max_consecutive_failures_) {
      ESP_LOGW(TAG, log_messages::RESETTING_PROTOCOL);
      active_protocol_.reset();  // Force protocol re-detection on next update
      consecutive_failures_ = 0;
    }
  }
}

void UpsHidComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "UPS HID Component:");
  ESP_LOGCONFIG(TAG, "  Simulation Mode: %s", simulation_mode_ ? status::YES : status::NO);
  
  if (transport_ && transport_->is_connected()) {
    ESP_LOGCONFIG(TAG, "  USB Vendor ID: 0x%04X", transport_->get_vendor_id());
    ESP_LOGCONFIG(TAG, "  USB Product ID: 0x%04X", transport_->get_product_id());
  }
  
  ESP_LOGCONFIG(TAG, "  Protocol Timeout: %u ms", static_cast<unsigned int>(protocol_timeout_ms_));
  ESP_LOGCONFIG(TAG, "  Protocol Selection: %s", protocol_selection_.c_str());
  ESP_LOGCONFIG(TAG, "  Update Interval: %u ms", static_cast<unsigned int>(get_update_interval()));

  if (transport_ && transport_->is_connected()) {
    ESP_LOGCONFIG(TAG, "  Status: %s", status::CONNECTED);
    if (active_protocol_) {
      ESP_LOGCONFIG(TAG, "  Active Protocol: %s", 
                   active_protocol_->get_protocol_name().c_str());
    } else {
      ESP_LOGCONFIG(TAG, "  Protocol Status: %s", status::DETECTION_PENDING);
    }
  } else {
    ESP_LOGCONFIG(TAG, "  Status: %s", status::DISCONNECTED);
  }

#ifdef USE_SENSOR
  ESP_LOGCONFIG(TAG, "  Registered Sensors: %zu", sensors_.size());
#endif
#ifdef USE_BINARY_SENSOR
  ESP_LOGCONFIG(TAG, "  Registered Binary Sensors: %zu", binary_sensors_.size());
#endif
#ifdef USE_TEXT_SENSOR
  ESP_LOGCONFIG(TAG, "  Registered Text Sensors: %zu", text_sensors_.size());
#endif
}

// Transport abstraction methods
esp_err_t UpsHidComponent::hid_get_report(uint8_t report_type, uint8_t report_id, 
                                         uint8_t* data, size_t* data_len, 
                                         uint32_t timeout_ms) {
  if (!transport_) {
    return ESP_ERR_INVALID_STATE;
  }
  return transport_->hid_get_report(report_type, report_id, data, data_len, timeout_ms);
}

esp_err_t UpsHidComponent::hid_set_report(uint8_t report_type, uint8_t report_id,
                                         const uint8_t* data, size_t data_len,
                                         uint32_t timeout_ms) {
  if (!transport_) {
    return ESP_ERR_INVALID_STATE;
  }
  return transport_->hid_set_report(report_type, report_id, data, data_len, timeout_ms);
}

esp_err_t UpsHidComponent::hid_interrupt_read(uint8_t* data, size_t* data_len, uint32_t timeout_ms) {
  if (!transport_) {
    return ESP_ERR_INVALID_STATE;
  }
  return transport_->hid_interrupt_read(data, data_len, timeout_ms);
}

esp_err_t UpsHidComponent::get_string_descriptor(uint8_t string_index, std::string& result) {
  if (!transport_) {
    return ESP_ERR_INVALID_STATE;
  }
  return transport_->get_string_descriptor(string_index, result);
}

bool UpsHidComponent::is_connected() const {
  return transport_ && transport_->is_connected();
}

uint16_t UpsHidComponent::get_vendor_id() const {
  return transport_ ? transport_->get_vendor_id() : defaults::AUTO_DETECT_VENDOR_ID;
}

uint16_t UpsHidComponent::get_product_id() const {
  return transport_ ? transport_->get_product_id() : defaults::AUTO_DETECT_PRODUCT_ID;
}

// Core implementation methods
bool UpsHidComponent::initialize_transport() {
  ESP_LOGD(TAG, "Initializing transport layer");
  
  // Create appropriate transport
  auto transport_type = simulation_mode_ ? 
    UsbTransportFactory::SIMULATION : 
    UsbTransportFactory::ESP32_HARDWARE;
    
  transport_ = UsbTransportFactory::create(transport_type, simulation_mode_);
  
  if (!transport_) {
    ESP_LOGE(TAG, "Failed to create transport instance");
    return false;
  }
  
  esp_err_t ret = transport_->initialize();
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Transport initialization failed: %s", transport_->get_last_error().c_str());
    transport_.reset();
    return false;
  }
  
  connected_ = transport_->is_connected();
  
  ESP_LOGI(TAG, "Transport initialized successfully (VID=0x%04X, PID=0x%04X)", 
           transport_->get_vendor_id(), transport_->get_product_id());
  
  return true;
}

bool UpsHidComponent::detect_protocol() {
  if (!transport_ || !transport_->is_connected()) {
    ESP_LOGE(TAG, "Cannot detect protocol - transport not connected");
    return false;
  }
  
  uint16_t vendor_id = transport_->get_vendor_id();
  
  if (protocol_selection_ == "auto") {
    // Automatic protocol detection based on vendor ID
    ESP_LOGD(TAG, "Auto-detecting protocol for vendor 0x%04X using factory", vendor_id);
    active_protocol_ = ProtocolFactory::create_for_vendor(vendor_id, this);
  } else {
    // Manual protocol selection via factory
    ESP_LOGD(TAG, "Using manually selected protocol: %s", protocol_selection_.c_str());
    active_protocol_ = ProtocolFactory::create_by_name(protocol_selection_, this);
  }
  
  if (!active_protocol_) {
    ESP_LOGE(TAG, "Failed to create protocol (selection: %s, vendor: 0x%04X)", 
             protocol_selection_.c_str(), vendor_id);
    return false;
  }
  
  ESP_LOGI(TAG, "Successfully created protocol: %s", active_protocol_->get_protocol_name().c_str());
  
  // Initialize the protocol (detection already done by factory)
  if (!active_protocol_->initialize()) {
    ESP_LOGE(TAG, "Protocol initialization failed");
    active_protocol_.reset();
    return false;
  }
  
  ESP_LOGI(TAG, "Protocol initialized: %s", 
           active_protocol_->get_protocol_name().c_str());
  
  // Set the detected protocol in ups_data_ after successful detection
  {
    std::lock_guard<std::mutex> lock(data_mutex_);
    ups_data_.device.detected_protocol = active_protocol_->get_protocol_type();
  }
  
  return true;
}

bool UpsHidComponent::read_ups_data() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for reading data");
    return false;
  }
  
  std::lock_guard<std::mutex> lock(data_mutex_);
  
  // Preserve the detected protocol before reset
  DeviceInfo::DetectedProtocol current_protocol = ups_data_.device.detected_protocol;
  
  // Reset data before reading
  ups_data_.reset();
  
  // Restore the detected protocol after reset
  ups_data_.device.detected_protocol = current_protocol;
  
  // Read data through protocol
  bool success = active_protocol_->read_data(ups_data_);
  
  if (success) {
    ESP_LOGV(TAG, "Successfully read UPS data");
  } else {
    ESP_LOGW(TAG, "Failed to read UPS data via protocol");
  }
  
  return success;
}

void UpsHidComponent::update_sensors() {
  std::lock_guard<std::mutex> lock(data_mutex_);
  
  // Check if any sensors are registered - if not, skip sensor updates
  size_t total_sensors = 0;
#ifdef USE_SENSOR
  total_sensors += sensors_.size();
#endif
#ifdef USE_BINARY_SENSOR
  total_sensors += binary_sensors_.size();
#endif
#ifdef USE_TEXT_SENSOR
  total_sensors += text_sensors_.size();
#endif
  
  if (total_sensors == 0) {
    // Data provider mode - no sensor entities, just providing data for direct access
    ESP_LOGVV(TAG, "Data provider mode: no sensors registered, data available via direct access methods");
    return;
  }
  
  ESP_LOGVV(TAG, "Updating %zu registered sensor entities", total_sensors);
  
  // Update all registered sensors with current data
#ifdef USE_SENSOR  
  for (auto& sensor_pair : sensors_) {
    const std::string& type = sensor_pair.first;
    sensor::Sensor* sensor = sensor_pair.second;
    
    // Extract appropriate value based on sensor type
    float value = NAN;
    
    if (type == sensor_type::BATTERY_LEVEL && ups_data_.battery.is_valid()) {
      value = ups_data_.battery.level;
    } else if (type == sensor_type::BATTERY_VOLTAGE && !std::isnan(ups_data_.battery.voltage)) {
      value = ups_data_.battery.voltage;
    } else if (type == sensor_type::BATTERY_VOLTAGE_NOMINAL && !std::isnan(ups_data_.battery.voltage_nominal)) {
      value = ups_data_.battery.voltage_nominal;
    } else if (type == sensor_type::RUNTIME && !std::isnan(ups_data_.battery.runtime_minutes)) {
      value = ups_data_.battery.runtime_minutes;
    } else if (type == sensor_type::INPUT_VOLTAGE && !std::isnan(ups_data_.power.input_voltage)) {
      value = ups_data_.power.input_voltage;
    } else if (type == sensor_type::INPUT_VOLTAGE_NOMINAL && !std::isnan(ups_data_.power.input_voltage_nominal)) {
      value = ups_data_.power.input_voltage_nominal;
    } else if (type == sensor_type::OUTPUT_VOLTAGE && !std::isnan(ups_data_.power.output_voltage)) {
      value = ups_data_.power.output_voltage;
    } else if (type == sensor_type::LOAD_PERCENT && !std::isnan(ups_data_.power.load_percent)) {
      value = ups_data_.power.load_percent;
    } else if (type == sensor_type::FREQUENCY && !std::isnan(ups_data_.power.frequency)) {
      value = ups_data_.power.frequency;
    } else if (type == sensor_type::INPUT_TRANSFER_LOW && !std::isnan(ups_data_.power.input_transfer_low)) {
      value = ups_data_.power.input_transfer_low;
    } else if (type == sensor_type::INPUT_TRANSFER_HIGH && !std::isnan(ups_data_.power.input_transfer_high)) {
      value = ups_data_.power.input_transfer_high;
    } else if (type == sensor_type::BATTERY_RUNTIME_LOW && !std::isnan(ups_data_.battery.runtime_low)) {
      value = ups_data_.battery.runtime_low;
    } else if (type == sensor_type::UPS_REALPOWER_NOMINAL && !std::isnan(ups_data_.power.realpower_nominal)) {
      value = ups_data_.power.realpower_nominal;
    } else if (type == sensor_type::UPS_DELAY_SHUTDOWN && !std::isnan(ups_data_.config.delay_shutdown)) {
      value = ups_data_.config.delay_shutdown;
    } else if (type == sensor_type::UPS_DELAY_START && !std::isnan(ups_data_.config.delay_start)) {
      value = ups_data_.config.delay_start;
    } else if (type == sensor_type::UPS_DELAY_REBOOT && !std::isnan(ups_data_.config.delay_reboot)) {
      value = ups_data_.config.delay_reboot;
    } else if (type == sensor_type::UPS_TIMER_REBOOT && ups_data_.test.timer_reboot != -1) {
      value = ups_data_.test.timer_reboot;
    } else if (type == sensor_type::UPS_TIMER_SHUTDOWN && ups_data_.test.timer_shutdown != -1) {
      value = ups_data_.test.timer_shutdown;
    } else if (type == sensor_type::UPS_TIMER_START && ups_data_.test.timer_start != -1) {
      value = ups_data_.test.timer_start;
    } else if (type == sensor_type::TEMPERATURE && !std::isnan(ups_data_.power.temperature)) {
      value = ups_data_.power.temperature;
    }
    
    if (!std::isnan(value)) {
      sensor->publish_state(value);
    }
  }
#endif
  
  // Update binary sensors
#ifdef USE_BINARY_SENSOR
  for (auto& sensor_pair : binary_sensors_) {
    const std::string& type = sensor_pair.first;
    binary_sensor::BinarySensor* sensor = sensor_pair.second;
    
    bool state = false;
    
    if (type == binary_sensor_type::ONLINE && ups_data_.power.input_voltage_valid()) {
      state = true;
    } else if (type == binary_sensor_type::ON_BATTERY && ups_data_.power.input_voltage_valid()) {
      state = false; // Opposite of online
    } else if (type == binary_sensor_type::LOW_BATTERY) {
      state = ups_data_.battery.is_low();
    }
    
    sensor->publish_state(state);
  }
#endif
  
  // Update text sensors
#ifdef USE_TEXT_SENSOR  
  for (auto& sensor_pair : text_sensors_) {
    const std::string& type = sensor_pair.first;
    text_sensor::TextSensor* sensor = sensor_pair.second;
    
    std::string value = "";
    
    if (type == text_sensor_type::MODEL && !ups_data_.device.model.empty()) {
      value = ups_data_.device.model;
    } else if (type == text_sensor_type::MANUFACTURER && !ups_data_.device.manufacturer.empty()) {
      value = ups_data_.device.manufacturer;
    } else if (type == text_sensor_type::SERIAL_NUMBER && !ups_data_.device.serial_number.empty()) {
      value = ups_data_.device.serial_number;
    } else if (type == text_sensor_type::FIRMWARE_VERSION && !ups_data_.device.firmware_version.empty()) {
      value = ups_data_.device.firmware_version;
    } else if (type == text_sensor_type::BATTERY_STATUS && !ups_data_.battery.status.empty()) {
      value = ups_data_.battery.status;
    } else if (type == text_sensor_type::UPS_TEST_RESULT && !ups_data_.test.ups_test_result.empty()) {
      value = ups_data_.test.ups_test_result;
    } else if (type == text_sensor_type::UPS_BEEPER_STATUS && !ups_data_.config.beeper_status.empty()) {
      value = ups_data_.config.beeper_status;
    } else if (type == text_sensor_type::INPUT_SENSITIVITY && !ups_data_.config.input_sensitivity.empty()) {
      value = ups_data_.config.input_sensitivity;
    } else if (type == text_sensor_type::STATUS && !ups_data_.power.status.empty()) {
      value = ups_data_.power.status;
    } else if (type == text_sensor_type::NUT_STATUS) {
      value = get_nut_status_locked();
    } else if (type == text_sensor_type::PROTOCOL) {
      value = get_protocol_name();
    } else if (type == text_sensor_type::BATTERY_MFR_DATE && !ups_data_.battery.mfr_date.empty()) {
      value = ups_data_.battery.mfr_date;
    } else if (type == text_sensor_type::UPS_MFR_DATE && !ups_data_.device.mfr_date.empty()) {
      value = ups_data_.device.mfr_date;
    } else if (type == text_sensor_type::BATTERY_TYPE && !ups_data_.battery.type.empty()) {
      value = ups_data_.battery.type;
    } else if (type == text_sensor_type::UPS_FIRMWARE_AUX && !ups_data_.device.firmware_aux.empty()) {
      value = ups_data_.device.firmware_aux;
    }
    
    if (!value.empty()) {
      sensor->publish_state(value);
    }
  }
#endif
  
  // Update delay number components
  for (auto* delay_number : delay_numbers_) {
    if (delay_number != nullptr) {
      // Determine which delay value to use based on the delay type
      // This will be handled by the number component itself
      // We just need to trigger an update with the current config values
      // The number component will query the appropriate value
    }
  }
  
  // Log sensor counts (conditional on platform availability)
#ifdef USE_SENSOR
  size_t sensor_count = sensors_.size();
#else
  size_t sensor_count = 0;
#endif
#ifdef USE_BINARY_SENSOR
  size_t binary_sensor_count = binary_sensors_.size(); 
#else
  size_t binary_sensor_count = 0;
#endif
#ifdef USE_TEXT_SENSOR
  size_t text_sensor_count = text_sensors_.size();
#else
  size_t text_sensor_count = 0;
#endif
  
  ESP_LOGV(TAG, "Updated %zu sensors, %zu binary sensors, %zu text sensors", 
           sensor_count, binary_sensor_count, text_sensor_count);
}

// Sensor registration methods (conditional on platform availability)
#ifdef USE_SENSOR
void UpsHidComponent::register_sensor(sensor::Sensor *sens, const std::string &type) {
  sensors_[type] = sens;
  ESP_LOGD(TAG, "Registered sensor: %s", type.c_str());
}
#endif

#ifdef USE_BINARY_SENSOR
void UpsHidComponent::register_binary_sensor(binary_sensor::BinarySensor *sens, const std::string &type) {
  binary_sensors_[type] = sens;
  ESP_LOGD(TAG, "Registered binary sensor: %s", type.c_str());
}
#endif

#ifdef USE_TEXT_SENSOR
void UpsHidComponent::register_text_sensor(text_sensor::TextSensor *sens, const std::string &type) {
  text_sensors_[type] = sens;
  ESP_LOGD(TAG, "Registered text sensor: %s", type.c_str());
}
#endif

void UpsHidComponent::register_delay_number(UpsDelayNumber *number) {
  delay_numbers_.push_back(number);
  ESP_LOGD(TAG, "Registered delay number component");
}

// Test control methods
bool UpsHidComponent::start_battery_test_quick() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for battery test");
    return false;
  }
  return active_protocol_->start_battery_test_quick();
}

bool UpsHidComponent::start_battery_test_deep() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for battery test");
    return false;
  }
  return active_protocol_->start_battery_test_deep();
}

bool UpsHidComponent::stop_battery_test() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for battery test");
    return false;
  }
  return active_protocol_->stop_battery_test();
}

bool UpsHidComponent::start_ups_test() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for UPS test");
    return false;
  }
  return active_protocol_->start_ups_test();
}

bool UpsHidComponent::stop_ups_test() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for UPS test");
    return false;
  }
  return active_protocol_->stop_ups_test();
}

// Beeper control methods
bool UpsHidComponent::beeper_enable() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for beeper control");
    return false;
  }
  return active_protocol_->beeper_enable();
}

bool UpsHidComponent::beeper_disable() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for beeper control");
    return false;
  }
  return active_protocol_->beeper_disable();
}

bool UpsHidComponent::beeper_mute() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for beeper control");
    return false;
  }
  return active_protocol_->beeper_mute();
}

bool UpsHidComponent::beeper_test() {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for beeper control");
    return false;
  }
  return active_protocol_->beeper_test();
}

// Delay configuration methods
bool UpsHidComponent::set_shutdown_delay(int seconds) {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for delay configuration");
    return false;
  }
  return active_protocol_->set_shutdown_delay(seconds);
}

bool UpsHidComponent::set_start_delay(int seconds) {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for delay configuration");
    return false;
  }
  return active_protocol_->set_start_delay(seconds);
}

bool UpsHidComponent::set_reboot_delay(int seconds) {
  if (!active_protocol_) {
    ESP_LOGW(TAG, "No active protocol for delay configuration");
    return false;
  }
  return active_protocol_->set_reboot_delay(seconds);
}

// Additional protocol access method
std::string UpsHidComponent::get_protocol_name() const {
  if (active_protocol_) {
    return active_protocol_->get_protocol_name();
  }
  return protocol::NONE;
}


// Error rate limiting helpers
bool UpsHidComponent::should_log_error(ErrorRateLimit& limiter) {
  uint32_t now = millis();
  
  if (limiter.error_count < ErrorRateLimit::MAX_BURST) {
    limiter.error_count++;
    limiter.last_error_time = now;
    return true;
  }
  
  if (now - limiter.last_error_time > ErrorRateLimit::RATE_LIMIT_MS) {
    limiter.error_count = 1;
    limiter.suppressed_count = 0;
    limiter.last_error_time = now;
    return true;
  }
  
  limiter.suppressed_count++;
  return false;
}

void UpsHidComponent::log_suppressed_errors(ErrorRateLimit& limiter) {
  if (limiter.suppressed_count > 0) {
    ESP_LOGW(TAG, "Suppressed %u similar errors in the last %u ms", 
             static_cast<unsigned int>(limiter.suppressed_count),
             static_cast<unsigned int>(ErrorRateLimit::RATE_LIMIT_MS));
    limiter.suppressed_count = 0;
  }
}

void UpsHidComponent::cleanup() {
  if (transport_) {
    transport_->deinitialize();
    transport_.reset();
  }
  
  active_protocol_.reset();
  connected_ = false;
  
  ESP_LOGD(TAG, "Component cleanup completed");
}

// Timer polling implementation
void UpsHidComponent::check_and_update_timers() {
  if (!active_protocol_) return;
  
  uint32_t now = millis();
  
  // Check if we need to poll timers
  bool should_poll_timers = false;
  
  if (fast_polling_mode_) {
    // In fast polling mode, check every 2 seconds
    if (now - last_timer_poll_ >= FAST_POLL_INTERVAL_MS) {
      should_poll_timers = true;
    }
  } else {
    // Check if any timers might be active (less frequent check)
    if (now - last_timer_poll_ >= get_update_interval()) {
      should_poll_timers = true;
    }
  }
  
  if (should_poll_timers) {
    last_timer_poll_ = now;
    
    // Try to read timer data
    UpsData timer_data = ups_data_;  // Copy current data
    if (active_protocol_->read_timer_data(timer_data)) {
      // Update only timer-related fields
      {
        std::lock_guard<std::mutex> lock(data_mutex_);
        ups_data_.test.timer_shutdown = timer_data.test.timer_shutdown;
        ups_data_.test.timer_start = timer_data.test.timer_start;
        ups_data_.test.timer_reboot = timer_data.test.timer_reboot;
      }
      
      // Update fast polling mode based on timer activity
      bool timers_active = has_active_timers();
      if (timers_active != fast_polling_mode_) {
        set_fast_polling_mode(timers_active);
      }
      
      // Update timer sensors immediately when values change
      update_sensors();
    }
  }
}

bool UpsHidComponent::has_active_timers() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return (ups_data_.test.timer_shutdown > 0 || 
          ups_data_.test.timer_start > 0 || 
          ups_data_.test.timer_reboot > 0);
}

void UpsHidComponent::set_fast_polling_mode(bool enable) {
  if (enable != fast_polling_mode_) {
    fast_polling_mode_ = enable;
    if (enable) {
      ESP_LOGI(TAG, "Enabled fast polling for timer countdown");
    } else {
      ESP_LOGI(TAG, "Disabled fast polling, returning to normal interval");
    }
  }
}

// Convenient state getters for lambda expressions (no sensor entities required)
bool UpsHidComponent::is_online() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return is_online_locked();
}

bool UpsHidComponent::is_on_battery() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return is_on_battery_locked();
}

bool UpsHidComponent::is_low_battery() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return is_low_battery_locked();
}

bool UpsHidComponent::is_charging() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return is_charging_locked();
}

bool UpsHidComponent::is_online_locked() const {
  // Prefer an authoritative online/on-battery bit when the protocol can
  // report one directly (currently: Megatec/Q1). Otherwise fall back to
  // the input-voltage heuristic used by HID PDC-based protocols.
  if (ups_data_.power.on_battery_known) {
    return !ups_data_.power.on_battery;
  }
  // UPS is online when input voltage is valid (same logic as binary sensor update)
  return ups_data_.power.input_voltage_valid();
}

bool UpsHidComponent::is_on_battery_locked() const {
  if (ups_data_.power.on_battery_known) {
    return ups_data_.power.on_battery;
  }
  // UPS is on battery when NOT online (opposite of online state)
  return !ups_data_.power.input_voltage_valid();
}

bool UpsHidComponent::is_low_battery_locked() const {
  // Use battery's built-in low battery detection (percentage vs.
  // configured threshold), OR an explicit LOW status some protocols report
  // directly via a dedicated bit (e.g. Megatec/Q1's status byte bit 6,
  // "Battery Low") - those never populate charge_low/charge_warning
  // thresholds at all, so is_low() alone would never trigger for them.
  return ups_data_.battery.is_low() || ups_data_.battery.status == battery_status::LOW;
}

bool UpsHidComponent::is_charging_locked() const {
  // Charging when online AND battery level is not 100%
  return ups_data_.power.input_voltage_valid() && 
         ups_data_.battery.is_valid() && 
         !std::isnan(ups_data_.battery.level) && 
         ups_data_.battery.level < 100.0f;
}

bool UpsHidComponent::has_fault() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return has_fault_locked();
}

bool UpsHidComponent::has_fault_locked() const {
  // Check for various fault conditions based on available data
  return ups_data_.power.is_input_out_of_range() || 
         (!ups_data_.power.is_valid() && !ups_data_.battery.is_valid()) ||
         ups_data_.battery.status == battery_status::FAULT;
}

bool UpsHidComponent::is_overloaded() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  // Use power's built-in overload detection
  return ups_data_.power.is_overloaded();
}

std::string UpsHidComponent::get_nut_status() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return get_nut_status_locked();
}

std::string UpsHidComponent::get_nut_status_locked() const {
  std::string status;
  if (is_online_locked()) {
    status = "OL";  // Online
  } else if (is_on_battery_locked()) {
    status = "OB";  // On Battery
  }

  if (is_low_battery_locked()) {
    if (!status.empty()) status += " ";
    status += "LB";  // Low Battery
  }

  if (is_charging_locked()) {
    if (!status.empty()) status += " ";
    status += "CHRG";  // Charging
  } else if (is_on_battery_locked()) {
    // Standard NUT convention: a UPS running on battery (and therefore not
    // charging) is reported as actively discharging.
    if (!status.empty()) status += " ";
    status += "DISCHRG";  // Discharging
  }

  if (has_fault_locked()) {
    if (!status.empty()) status += " ";
    status += "ALARM";  // Alarm condition
  }

  return status;
}

float UpsHidComponent::get_battery_level() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return ups_data_.battery.is_valid() ? ups_data_.battery.level : NAN;
}

float UpsHidComponent::get_input_voltage() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return ups_data_.power.input_voltage;
}

float UpsHidComponent::get_output_voltage() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return ups_data_.power.output_voltage;
}

float UpsHidComponent::get_load_percent() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return ups_data_.power.load_percent;
}

float UpsHidComponent::get_temperature() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return ups_data_.power.temperature;
}

float UpsHidComponent::get_runtime_minutes() const {
  std::lock_guard<std::mutex> lock(data_mutex_);
  return ups_data_.battery.runtime_minutes;
}


} // namespace ups_hid
} // namespace esphome