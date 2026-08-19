#include "protocol_generic.h"
#include "ups_hid.h"
#include "constants_hid.h"
#include "constants_ups.h"
#include "esphome/core/log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/portmacro.h"
#include <set>
#include <map>
#include <algorithm>
#include <cmath>

namespace esphome {
namespace ups_hid {

static const char *const GEN_TAG = "ups_hid.generic";

// Common HID Power Device report IDs based on NUT analysis
// These are the most frequently used report IDs across different UPS vendors
static const uint8_t COMMON_REPORT_IDS[] = {
  0x01, // General status (widely used)
  0x06, // Battery status (APC and others)
  0x0C, // Power summary (battery % + runtime)
  0x16, // Present status bitmap
  0x30, // Input measurements
  0x31, // Output measurements  
  0x40, // Battery system
  0x50, // Load percentage
};

// Extended search range for enumeration
static const uint8_t EXTENDED_REPORT_IDS[] = {
  0x02, 0x03, 0x04, 0x05, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0D, 0x0E, 0x0F,
  0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C,
  0x20, 0x21, 0x22, 0x32, 0x33, 0x35, 0x42, 0x43, 0x44, 0x45,
};

// Report type constants for HID
// HID report types are now defined in hid_constants.h

bool GenericHidProtocol::detect() {
  ESP_LOGD(GEN_TAG, "Detecting Generic HID Protocol...");
  
  // Check device connection status first
  if (!parent_->is_connected()) {
    ESP_LOGD(GEN_TAG, "Device not connected, skipping protocol detection");
    return false;
  }
  
  // Check if this is a known vendor that should use a specific protocol
  uint16_t vid = parent_->get_vendor_id();
  if (vid == usb::VENDOR_ID_APC || vid == usb::VENDOR_ID_CYBERPOWER) { // APC or CyberPower
    ESP_LOGD(GEN_TAG, "Known vendor 0x%04X should use specific protocol", vid);
    return false;
  }
  
  // Try common report IDs to detect HID Power Device
  uint8_t buffer[limits::MIN_HID_REPORT_SIZE];
  size_t buffer_len;
  
  for (uint8_t report_id : COMMON_REPORT_IDS) {
    // Check connection status before each attempt
    if (!parent_->is_connected()) {
      ESP_LOGD(GEN_TAG, "Device disconnected during protocol detection");
      return false;
    }
    
    // Try Input Report first (real-time data)
    buffer_len = sizeof(buffer);
    esp_err_t ret = parent_->hid_get_report(HID_REPORT_TYPE_INPUT, report_id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0) {
      available_input_reports_.insert(report_id);
      ESP_LOGI(GEN_TAG, "Found Input report 0x%02X (%zu bytes)", report_id, buffer_len);
      report_sizes_[report_id] = buffer_len;
      return true;
    }
    
    // Check connection again before trying Feature report
    if (!parent_->is_connected()) {
      ESP_LOGD(GEN_TAG, "Device disconnected during protocol detection");
      return false;
    }
    
    // Try Feature Report (static/configuration data)
    buffer_len = sizeof(buffer);
    ret = parent_->hid_get_report(HID_REPORT_TYPE_FEATURE, report_id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0) {
      available_feature_reports_.insert(report_id);
      ESP_LOGI(GEN_TAG, "Found Feature report 0x%02X (%zu bytes)", report_id, buffer_len);
      report_sizes_[report_id] = buffer_len;
      return true;
    }
    
    // Small delay to avoid overwhelming the device
    vTaskDelay(pdMS_TO_TICKS(timing::EXTENDED_DISCOVERY_DELAY_MS));
  }
  
  ESP_LOGD(GEN_TAG, "No standard HID Power Device reports found");
  return false;
}

bool GenericHidProtocol::initialize() {
  ESP_LOGD(GEN_TAG, "Initializing Generic HID Protocol...");
  
  // Clear any previous state
  available_input_reports_.clear();
  available_feature_reports_.clear();
  report_sizes_.clear();
  
  // Enumerate available reports
  enumerate_reports();
  
  if (available_input_reports_.empty() && available_feature_reports_.empty()) {
    ESP_LOGE(GEN_TAG, "No HID reports found during initialization");
    return false;
  }
  
  ESP_LOGI(GEN_TAG, "Generic HID initialized with %zu input and %zu feature reports",
           available_input_reports_.size(), available_feature_reports_.size());
  
  // Log discovered reports for debugging
  ESP_LOGD(GEN_TAG, "Input reports:");
  for (uint8_t id : available_input_reports_) {
    ESP_LOGD(GEN_TAG, "  0x%02X: %zu bytes", id, report_sizes_[id]);
  }
  ESP_LOGD(GEN_TAG, "Feature reports:");
  for (uint8_t id : available_feature_reports_) {
    ESP_LOGD(GEN_TAG, "  0x%02X: %zu bytes", id, report_sizes_[id]);
  }
  
  return true;
}

bool GenericHidProtocol::read_data(UpsData &data) {
  ESP_LOGV(GEN_TAG, "Reading Generic HID UPS data...");
  
  bool success = false;
  uint8_t buffer[limits::MAX_HID_REPORT_SIZE];
  size_t buffer_len;
  
  // Try to read known report types in priority order
  
  // 1. Power Summary (0x0C) - Battery % and runtime (highest priority)
  if (read_report(0x0C, buffer, buffer_len)) {
    parse_power_summary(buffer, buffer_len, data);
    success = true;
  }
  
  // 2. Battery status (0x06) - Alternative battery info
  if (read_report(0x06, buffer, buffer_len)) {
    parse_battery_status(buffer, buffer_len, data);
    success = true;
  }
  
  // 3. Present Status (0x16) - Status flags
  if (read_report(0x16, buffer, buffer_len)) {
    parse_present_status(buffer, buffer_len, data);
    success = true;
  }
  
  // 4. General status (0x01) - Common status report
  if (read_report(0x01, buffer, buffer_len)) {
    parse_general_status(buffer, buffer_len, data);
    success = true;
  }

  // 5. Input and Output voltages
  // Report 0x30 is typically input voltage
  if (read_report(HID_USAGE_POW_VOLTAGE, buffer, buffer_len))
  {                                                // 0x30
    parse_voltage(buffer, buffer_len, data, true); // Parse as input
    success = true;
  }

  // Report 0x31 is typically output voltage (or sometimes current)
  if (read_report(0x31, buffer, buffer_len))
  { // Use direct report ID for output voltage/current
    // Try to parse as output voltage first
    parse_voltage(buffer, buffer_len, data, false); // Parse as output
    success = true;
  }

  // 6. Load percentage - try multiple report IDs
  if (!std::isnan(data.power.load_percent))
  {
    // Check if load percentage was already set by previous parsing
    ESP_LOGV(GEN_TAG, "Load percentage already set: %.1f%%", data.power.load_percent);
  }
  else
  {
    read_load_percentage(data);
    if (!std::isnan(data.power.load_percent))
    {
      success = true;
    }
  }

  // 7. Input sensitivity - use separate reports from load percentage
  if (read_report(0x1a, buffer, buffer_len))
  {
    parse_input_sensitivity(buffer, buffer_len, data, "CyberPower-style");
    success = true;
  }
  else if (read_report(0x34, buffer, buffer_len))
  { // Use 0x34 instead of 0x35 to avoid conflict
    parse_input_sensitivity(buffer, buffer_len, data, "APC-style");
    success = true;
  }

  // 8. Try to read frequency data
  float prev_frequency = data.power.frequency;
  read_frequency_data(data);
  if (!std::isnan(data.power.frequency) && std::isnan(prev_frequency))
  {
    success = true;
  }

  // 9. Try to read delay configuration values
  bool prev_has_delays = data.config.has_timing_config();
  read_delay_configuration(data);
  if (data.config.has_timing_config() && !prev_has_delays)
  {
    success = true;
  }

  // 10. Try to read beeper status
  bool prev_has_beeper = data.config.has_beeper_config();
  read_beeper_status(data);
  if (data.config.has_beeper_config() && !prev_has_beeper)
  {
    success = true;
  }

  // 11. Try any other discovered reports with heuristic parsing
  if (!success)
  {
    for (uint8_t id : available_input_reports_)
    {
      if (id == 0x01 || id == 0x06 || id == 0x0C || id == 0x16 ||
          id == 0x30 || id == 0x31 || id == 0x50 || id == 0x1A || id == 0x35)
      {
        continue; // Already tried
      }

      if (read_report(id, buffer, buffer_len))
      {
        ESP_LOGV(GEN_TAG, "Trying heuristic parsing for report 0x%02X", id);
        if (parse_unknown_report(buffer, buffer_len, data))
        {
          success = true;
          break;
        }
      }
    }
  }

  // Set generic manufacturer/model if not already set
  if (data.device.manufacturer.empty())
  {
    data.device.manufacturer = protocol::GENERIC;
  }
  if (data.device.model.empty())
  {
    uint16_t vid = parent_->get_vendor_id();
    uint16_t pid = parent_->get_product_id();
    char model_str[32];
    snprintf(model_str, sizeof(model_str), "HID UPS %04X:%04X", vid, pid);
    data.device.model = model_str;
  }

  // Ensure we have at least basic power status
  if (success && data.power.status.empty())
  {
    // If we got data but no power status, assume online
    data.power.status = status::ONLINE;
    data.power.input_voltage = parent_->get_fallback_nominal_voltage(); // Use configured fallback voltage
  }

  // Set default test result
  data.test.ups_test_result = test::RESULT_NO_TEST;

  return success;
}

void GenericHidProtocol::enumerate_reports()
{
  ESP_LOGD(GEN_TAG, "Enumerating HID reports...");

  uint8_t buffer[limits::MAX_HID_REPORT_SIZE];
  size_t buffer_len;
  int discovered_count = 0;

  // First try common report IDs
  for (uint8_t id : COMMON_REPORT_IDS)
  {
    // Check device connection before each report
    if (!parent_->is_connected())
    {
      ESP_LOGD(GEN_TAG, "Device disconnected during report enumeration");
      return;
    }

    // Check Input reports
    buffer_len = sizeof(buffer);
    esp_err_t ret = parent_->hid_get_report(HID_REPORT_TYPE_INPUT, id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0)
    {
      available_input_reports_.insert(id);
      report_sizes_[id] = buffer_len;
      discovered_count++;
      ESP_LOGV(GEN_TAG, "Found Input report 0x%02X (%zu bytes)", id, buffer_len);
    }

    // Check connection again before Feature report
    if (!parent_->is_connected())
    {
      ESP_LOGD(GEN_TAG, "Device disconnected during report enumeration");
      return;
    }

    // Check Feature reports
    buffer_len = sizeof(buffer);
    ret = parent_->hid_get_report(HID_REPORT_TYPE_FEATURE, id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0)
    {
      available_feature_reports_.insert(id);
      if (report_sizes_.find(id) == report_sizes_.end())
      {
        report_sizes_[id] = buffer_len;
      }
      discovered_count++;
      ESP_LOGV(GEN_TAG, "Found Feature report 0x%02X (%zu bytes)", id, buffer_len);
    }

    vTaskDelay(pdMS_TO_TICKS(timing::REPORT_DISCOVERY_DELAY_MS));
  }

  // If we found enough reports, skip extended search
  if (discovered_count >= limits::MAX_DISCOVERY_ATTEMPTS)
  {
    ESP_LOGD(GEN_TAG, "Found %d reports, skipping extended search", discovered_count);
    return;
  }

  // Extended search for less common report IDs
  ESP_LOGD(GEN_TAG, "Performing extended report search...");
  for (uint8_t id : EXTENDED_REPORT_IDS)
  {
    // Check device connection before each extended report
    if (!parent_->is_connected())
    {
      ESP_LOGD(GEN_TAG, "Device disconnected during extended report search");
      return;
    }

    // Limit total discovery time
    if (discovered_count >= limits::MAX_EXTENDED_DISCOVERY_ATTEMPTS)
    {
      break;
    }

    buffer_len = sizeof(buffer);
    esp_err_t ret = parent_->hid_get_report(HID_REPORT_TYPE_INPUT, id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0)
    {
      available_input_reports_.insert(id);
      report_sizes_[id] = buffer_len;
      discovered_count++;
      ESP_LOGV(GEN_TAG, "Found Input report 0x%02X (%zu bytes)", id, buffer_len);
    }

    vTaskDelay(pdMS_TO_TICKS(timing::REPORT_DISCOVERY_DELAY_MS));
  }

  ESP_LOGD(GEN_TAG, "Enumeration complete: found %d reports", discovered_count);
}

bool GenericHidProtocol::read_report(uint8_t report_id, uint8_t *buffer, size_t &buffer_len)
{
  // Try Input report first if available (real-time data)
  if (available_input_reports_.count(report_id))
  {
    buffer_len = limits::MAX_HID_REPORT_SIZE;
    esp_err_t ret = parent_->hid_get_report(HID_REPORT_TYPE_INPUT, report_id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0)
    {
      ESP_LOGV(GEN_TAG, "Read Input report 0x%02X: %zu bytes", report_id, buffer_len);
      return true;
    }
  }

  // Try Feature report (static/configuration data)
  if (available_feature_reports_.count(report_id))
  {
    buffer_len = limits::MAX_HID_REPORT_SIZE;
    esp_err_t ret = parent_->hid_get_report(HID_REPORT_TYPE_FEATURE, report_id, buffer, &buffer_len, parent_->get_protocol_timeout());
    if (ret == ESP_OK && buffer_len > 0)
    {
      ESP_LOGV(GEN_TAG, "Read Feature report 0x%02X: %zu bytes", report_id, buffer_len);
      return true;
    }
  }

  return false;
}

// Parse methods following HID Power Device Class specification patterns
void GenericHidProtocol::parse_power_summary(uint8_t *data, size_t len, UpsData &ups_data)
{
  // Report 0x0C typically contains battery % and runtime
  // Format observed: [0x0C, battery%, runtime_low, runtime_high, ...]
  if (len >= 2)
  {
    // Battery percentage typically at byte 1
    uint8_t battery = data[1];
    if (battery <= 100)
    {
      ups_data.battery.level = static_cast<float>(battery);
      ESP_LOGD(GEN_TAG, "Power summary: Battery %d%%", battery);
    }
    else if (battery <= battery::ALTERNATIVE_PERCENTAGE_SCALE && battery > 100)
    {
      // Some devices use 0-200 scale
      ups_data.battery.level = static_cast<float>(battery) / (battery::ALTERNATIVE_PERCENTAGE_SCALE / battery::MAX_LEVEL_PERCENT);
      ESP_LOGD(GEN_TAG, "Power summary: Battery %.1f%% (scaled from %d)", ups_data.battery.level, battery);
    }
  }

  if (len >= 4)
  {
    // Runtime value (16-bit little-endian at bytes 2-3)
    // Most UPS devices report runtime in seconds, not minutes
    uint16_t runtime_raw = data[2] | (data[3] << 8);

    if (runtime_raw > 0 && runtime_raw < 65535)
    {
      // Determine if value is in seconds or minutes based on magnitude
      // Values > 180 are likely seconds (3+ minutes), values <= 180 could be minutes
      if (runtime_raw > 180)
      {
        // Convert seconds to minutes for ESPHome sensor expectation
        ups_data.battery.runtime_minutes = static_cast<float>(runtime_raw) / 60.0f;
        ESP_LOGD(GEN_TAG, "Power summary: Runtime %.1f minutes (from %d seconds)",
                 ups_data.battery.runtime_minutes, runtime_raw);
      }
      else
      {
        // Assume value is already in minutes
        ups_data.battery.runtime_minutes = static_cast<float>(runtime_raw);
        ESP_LOGD(GEN_TAG, "Power summary: Runtime %d minutes", runtime_raw);
      }
    }
  }
}

void GenericHidProtocol::parse_battery_status(uint8_t *data, size_t len, UpsData &ups_data)
{
  // Report 0x06 typically contains battery status information
  if (len >= 2)
  {
    uint8_t status = data[1];

    // Common battery status bits (varies by vendor)
    if (status != 0xFF && status != 0x00)
    { // Valid status
      // Update power status
      if (status & 0x01)
      {
        ups_data.power.status = status::ONLINE;
        ups_data.power.input_voltage = parent_->get_fallback_nominal_voltage(); // Use configured fallback voltage
      }
      if (status & 0x02)
      {
        ups_data.power.status = status::ON_BATTERY;
        ups_data.power.input_voltage = NAN;
      }

      // Update battery status with improved logic
      // Check if battery is at 100% to determine if fully charged
      bool is_fully_charged = !std::isnan(ups_data.battery.level) && ups_data.battery.level >= 100.0f;

      if (status & 0x08)
      {
        // Bit indicates charging or fully charged
        if (is_fully_charged)
        {
          ups_data.battery.status = battery_status::FULLY_CHARGED;
        }
        else
        {
          ups_data.battery.status = battery_status::CHARGING;
        }
      }
      else if (is_fully_charged)
      {
        // Not charging but at 100% - likely fully charged
        ups_data.battery.status = battery_status::FULLY_CHARGED;
      }

      if (status & 0x04)
      {
        ups_data.battery.charge_low = battery::LOW_THRESHOLD_PERCENT; // Low battery threshold
        // Also update status to indicate low battery condition
        if (ups_data.battery.status.empty())
        {
          ups_data.battery.status = battery_status::LOW;
        }
        else if (ups_data.battery.status.find(battery_status::LOW) == std::string::npos)
        {
          ups_data.battery.status += " - " + std::string(battery_status::LOW);
        }
      }

      if (status & 0x10)
      {
        // Append replace battery suffix to existing status
        if (ups_data.battery.status.empty())
        {
          ups_data.battery.status = std::string(battery_status::NORMAL) + battery_status::REPLACE_BATTERY_SUFFIX;
        }
        else
        {
          ups_data.battery.status += battery_status::REPLACE_BATTERY_SUFFIX;
        }
      }

      ESP_LOGD(GEN_TAG, "Battery status: 0x%02X -> Power: \"%s\", Battery: \"%s\"",
               status, ups_data.power.status.c_str(), ups_data.battery.status.c_str());
    }
  }

  // Some devices include battery level here too
  if (len >= 3 && std::isnan(ups_data.battery.level))
  {
    uint8_t battery = data[2];
    if (battery <= 100)
    {
      ups_data.battery.level = static_cast<float>(battery);
      ESP_LOGD(GEN_TAG, "Battery status: Battery %d%%", battery);
    }
  }
}

void GenericHidProtocol::parse_present_status(uint8_t *data, size_t len, UpsData &ups_data)
{
  // Report 0x16 typically contains present status bitmap
  // Based on HID Power Device spec, these are common bit positions
  if (len >= 2)
  {
    uint8_t status = data[1];

    // Validate status - 0xFF and 0x00 are often invalid/uninitialized values
    if (status == 0xFF || status == 0x00)
    {
      ESP_LOGD(GEN_TAG, "Invalid present status: 0x%02X - ignoring", status);
      return;
    }

    // Standard HID Power Device status bits - map to data structures
    if (status & 0x01)
    {
      ups_data.battery.status = battery_status::CHARGING;
    }

    if (status & 0x02)
    {
      ups_data.power.status = status::ON_BATTERY;
      ups_data.power.input_voltage = NAN;
    }

    if (status & 0x04)
    {
      ups_data.power.status = status::ONLINE;
      ups_data.power.input_voltage = parent_->get_fallback_nominal_voltage(); // Use configured fallback voltage
    }

    if (status & 0x08)
    {
      ups_data.battery.charge_low = battery::LOW_THRESHOLD_PERCENT; // Low battery threshold
      // Also update status to indicate low battery condition
      if (ups_data.battery.status.empty())
      {
        ups_data.battery.status = battery_status::LOW;
      }
      else if (ups_data.battery.status.find(battery_status::LOW) == std::string::npos)
      {
        ups_data.battery.status += " - " + std::string(battery_status::LOW);
      }
    }

    if (status & 0x10)
    {
      // Append replace battery suffix to existing status
      if (ups_data.battery.status.empty())
      {
        ups_data.battery.status = std::string(battery_status::NORMAL) + battery_status::REPLACE_BATTERY_SUFFIX;
      }
      else
      {
        ups_data.battery.status += battery_status::REPLACE_BATTERY_SUFFIX;
      }
    }

    if (status & 0x20)
    {
      // Append overload status to power status
      if (ups_data.power.status.empty())
      {
        ups_data.power.status = std::string(status::ONLINE) + " - Overload";
      }
      else
      {
        ups_data.power.status += " - Overload";
      }
    }

    if (status & 0x40)
    {
      // Append fault suffix to battery status
      if (ups_data.battery.status.empty())
      {
        ups_data.battery.status = std::string(battery_status::FAULT) + battery_status::FAULT_SUFFIX;
      }
      else
      {
        ups_data.battery.status += battery_status::FAULT_SUFFIX;
      }
    }

    ESP_LOGD(GEN_TAG, "Present status: 0x%02X -> Power: \"%s\", Battery: \"%s\"",
             status, ups_data.power.status.c_str(), ups_data.battery.status.c_str());
  }
}

void GenericHidProtocol::parse_general_status(uint8_t *data, size_t len, UpsData &ups_data)
{
  // Report 0x01 is often a general status report
  if (len >= 2)
  {
    // Try to extract basic status
    uint8_t byte1 = data[1];

    // Different vendors use different bit patterns, try common ones
    if (byte1 & 0x01)
    {
      ups_data.power.status = status::ONLINE;
      ups_data.power.input_voltage = parent_->get_fallback_nominal_voltage(); // Use configured fallback voltage
    }
    if (byte1 & 0x10)
    {
      ups_data.power.status = status::ON_BATTERY;
      ups_data.power.input_voltage = NAN;
    }

    ESP_LOGV(GEN_TAG, "General status byte: 0x%02X -> Power: \"%s\"", byte1, ups_data.power.status.c_str());
  }
}

void GenericHidProtocol::parse_voltage(uint8_t *data, size_t len, UpsData &ups_data, bool is_input)
{
  if (len >= 3)
  {
    // Common pattern: 16-bit value at bytes 1-2 (little-endian)
    uint16_t voltage_raw = data[1] | (data[2] << 8);

    // Validate against invalid values
    if (voltage_raw == 0xFFFF || voltage_raw == 0x0000)
    {
      ESP_LOGV(GEN_TAG, "Invalid voltage value 0x%04X - ignoring", voltage_raw);
      return;
    }

    float voltage = static_cast<float>(voltage_raw);

    // Auto-detect scaling
    if (voltage > 1000)
    {
      voltage /= 10.0f; // Some devices use 0.1V units (tenths of volts)
    }
    else if (voltage > 100 && voltage < 1000)
    {
      // Check if this might be in tenths of volts already
      float test_voltage = voltage / 10.0f;
      if (test_voltage >= voltage::MIN_VALID_VOLTAGE && test_voltage <= voltage::MAX_VALID_VOLTAGE)
      {
        voltage = test_voltage;
      }
    }

    // Sanity check - validate voltage is in reasonable range
    if (voltage >= voltage::MIN_VALID_VOLTAGE && voltage <= voltage::MAX_VALID_VOLTAGE)
    {
      if (is_input)
      {
        ups_data.power.input_voltage = voltage;
        ESP_LOGD(GEN_TAG, "Input voltage: %.1fV (from raw 0x%04X)", voltage, voltage_raw);
      }
      else
      {
        ups_data.power.output_voltage = voltage;
        ESP_LOGD(GEN_TAG, "Output voltage: %.1fV (from raw 0x%04X)", voltage, voltage_raw);
      }
    }
    else
    {
      ESP_LOGV(GEN_TAG, "Voltage %.1fV out of valid range (%.1f-%.1fV) - ignoring",
               voltage, voltage::MIN_VALID_VOLTAGE, voltage::MAX_VALID_VOLTAGE);
    }
  }
}

bool GenericHidProtocol::parse_unknown_report(uint8_t *data, size_t len, UpsData &ups_data)
{
  // Heuristic parsing for unknown reports
  bool found_data = false;

  // Look for percentage values (0-100)
  for (size_t i = 1; i < len && i < 4; i++)
  {
    if (data[i] <= 100 && data[i] > 0)
    {
      if (std::isnan(ups_data.battery.level))
      {
        ups_data.battery.level = static_cast<float>(data[i]);
        ESP_LOGV(GEN_TAG, "Heuristic: Found possible battery level %d%% at byte %zu", data[i], i);
        found_data = true;
      }
      else if (std::isnan(ups_data.power.load_percent))
      {
        ups_data.power.load_percent = static_cast<float>(data[i]);
        ESP_LOGV(GEN_TAG, "Heuristic: Found possible load %d%% at byte %zu", data[i], i);
        found_data = true;
      }
    }
  }

  // Look for voltage values (16-bit, 80-300V range)
  for (size_t i = 1; i <= len - 2; i++)
  {
    uint16_t value = data[i] | (data[i + 1] << 8);
    float voltage = static_cast<float>(value);

    // Try direct and scaled
    if (voltage > 1000)
      voltage /= 10.0f;

    if (voltage >= voltage::MIN_VALID_VOLTAGE && voltage <= voltage::MAX_VALID_VOLTAGE)
    {
      if (std::isnan(ups_data.power.input_voltage))
      {
        ups_data.power.input_voltage = voltage;
        ESP_LOGV(GEN_TAG, "Heuristic: Found possible voltage %.1fV at bytes %zu-%zu",
                 voltage, i, i + 1);
        found_data = true;
      }
    }
  }

  return found_data;
}

void GenericHidProtocol::parse_input_sensitivity(uint8_t *data, size_t len, UpsData &ups_data, const char *style)
{
  if (len < 2)
  {
    ESP_LOGV(GEN_TAG, "Input sensitivity report too short: %zu bytes", len);
    return;
  }

  uint8_t sensitivity_raw = data[1];
  ESP_LOGD(GEN_TAG, "Raw input sensitivity (%s): 0x%02X (%d)", style, sensitivity_raw, sensitivity_raw);

  // DYNAMIC GENERIC SENSITIVITY MAPPING
  switch (sensitivity_raw)
  {
  case 0:
    ups_data.config.input_sensitivity = sensitivity::HIGH;
    ESP_LOGI(GEN_TAG, "Generic input sensitivity (%s): %s (raw: %d)", style, sensitivity::HIGH, sensitivity_raw);
    break;
  case 1:
    ups_data.config.input_sensitivity = sensitivity::NORMAL;
    ESP_LOGI(GEN_TAG, "Generic input sensitivity (%s): %s (raw: %d)", style, sensitivity::NORMAL, sensitivity_raw);
    break;
  case 2:
    ups_data.config.input_sensitivity = sensitivity::LOW;
    ESP_LOGI(GEN_TAG, "Generic input sensitivity (%s): %s (raw: %d)", style, sensitivity::LOW, sensitivity_raw);
    break;
  case 3:
    ups_data.config.input_sensitivity = sensitivity::AUTO;
    ESP_LOGI(GEN_TAG, "Generic input sensitivity (%s): %s (raw: %d)", style, sensitivity::AUTO, sensitivity_raw);
    break;
  default:
    // GENERIC DYNAMIC HANDLING: For unknown values, be more permissive
    if (sensitivity_raw >= 100)
    {
      // Large values likely indicate wrong report format or encoding
      ESP_LOGW(GEN_TAG, "Unexpected large sensitivity value (%s): %d (0x%02X)",
               style, sensitivity_raw, sensitivity_raw);

      // Try alternative byte positions for generic devices
      for (size_t i = 2; i < len && i < 5; i++)
      {
        uint8_t alt_value = data[i];
        if (alt_value <= 3)
        {
          switch (alt_value)
          {
          case 0:
            ups_data.config.input_sensitivity = sensitivity::HIGH;
            break;
          case 1:
            ups_data.config.input_sensitivity = sensitivity::NORMAL;
            break;
          case 2:
            ups_data.config.input_sensitivity = sensitivity::LOW;
            break;
          case 3:
            ups_data.config.input_sensitivity = sensitivity::AUTO;
            break;
          }
          ESP_LOGI(GEN_TAG, "Generic input sensitivity (%s, alt byte[%zu]): %s (raw: %d)",
                   style, i, ups_data.config.input_sensitivity.c_str(), alt_value);
          return;
        }
      }

      // Fallback to reasonable default
      ups_data.config.input_sensitivity = sensitivity::NORMAL;
      ESP_LOGW(GEN_TAG, "Using default 'normal' sensitivity (%s) due to unexpected value: %d",
               style, sensitivity_raw);
    }
    else
    {
      // Values 4-99 - provide extended mapping for unknown devices
      if (sensitivity_raw <= 10)
      {
        // Map to nearest known value
        if (sensitivity_raw <= 3)
        {
          ups_data.config.input_sensitivity = sensitivity::HIGH;
        }
        else if (sensitivity_raw <= 6)
        {
          ups_data.config.input_sensitivity = sensitivity::NORMAL;
        }
        else
        {
          ups_data.config.input_sensitivity = sensitivity::LOW;
        }
        ESP_LOGI(GEN_TAG, "Generic input sensitivity (%s, mapped): %s (raw: %d)",
                 style, ups_data.config.input_sensitivity.c_str(), sensitivity_raw);
      }
      else
      {
        ups_data.config.input_sensitivity = sensitivity::UNKNOWN;
        ESP_LOGW(GEN_TAG, "Unknown generic sensitivity value (%s): %d", style, sensitivity_raw);
      }
    }
    break;
  }
}

// Generic HID test implementations (basic functionality for unknown devices)
bool GenericHidProtocol::start_battery_test_quick()
{
  ESP_LOGI(GEN_TAG, "Starting Generic HID quick battery test");

  // Try common test report IDs used by various UPS vendors
  // Based on NUT analysis: report IDs 0x14 (CyberPower), 0x52 (APC), and common alternatives
  uint8_t test_report_ids[] = {0x14, 0x52, 0x0f, 0x1a};

  for (size_t i = 0; i < sizeof(test_report_ids); i++)
  {
    uint8_t report_id = test_report_ids[i];
    uint8_t test_data[2] = {report_id, test::COMMAND_QUICK}; // Command value 1 = Quick test

    ESP_LOGD(GEN_TAG, "Trying quick battery test with report ID 0x%02X", report_id);
    esp_err_t ret = parent_->hid_set_report(0x03, report_id, test_data, sizeof(test_data), parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(GEN_TAG, "Generic quick battery test command sent with report ID 0x%02X", report_id);
      return true;
    }
    else
    {
      ESP_LOGD(GEN_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }

  ESP_LOGW(GEN_TAG, "Failed to send generic quick battery test with all tried report IDs");
  return false;
}

bool GenericHidProtocol::start_battery_test_deep()
{
  ESP_LOGI(GEN_TAG, "Starting Generic HID deep battery test");

  // Try common test report IDs used by various UPS vendors
  uint8_t test_report_ids[] = {0x14, 0x52, 0x0f, 0x1a};

  for (size_t i = 0; i < sizeof(test_report_ids); i++)
  {
    uint8_t report_id = test_report_ids[i];
    uint8_t test_data[2] = {report_id, test::COMMAND_DEEP}; // Command value 2 = Deep test

    ESP_LOGD(GEN_TAG, "Trying deep battery test with report ID 0x%02X", report_id);
    esp_err_t ret = parent_->hid_set_report(0x03, report_id, test_data, sizeof(test_data), parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(GEN_TAG, "Generic deep battery test command sent with report ID 0x%02X", report_id);
      return true;
    }
    else
    {
      ESP_LOGD(GEN_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }

  ESP_LOGW(GEN_TAG, "Failed to send generic deep battery test with all tried report IDs");
  return false;
}

bool GenericHidProtocol::stop_battery_test()
{
  ESP_LOGI(GEN_TAG, "Stopping Generic HID battery test");

  // Try common test report IDs used by various UPS vendors
  uint8_t test_report_ids[] = {0x14, 0x52, 0x0f, 0x1a};

  for (size_t i = 0; i < sizeof(test_report_ids); i++)
  {
    uint8_t report_id = test_report_ids[i];
    uint8_t test_data[2] = {report_id, test::COMMAND_ABORT}; // Command value 3 = Abort test

    ESP_LOGD(GEN_TAG, "Trying battery test stop with report ID 0x%02X", report_id);
    esp_err_t ret = parent_->hid_set_report(0x03, report_id, test_data, sizeof(test_data), parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(GEN_TAG, "Generic battery test stop command sent with report ID 0x%02X", report_id);
      return true;
    }
    else
    {
      ESP_LOGD(GEN_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }

  ESP_LOGW(GEN_TAG, "Failed to send generic battery test stop with all tried report IDs");
  return false;
}

bool GenericHidProtocol::start_ups_test()
{
  ESP_LOGI(GEN_TAG, "Starting Generic HID UPS test");

  // Try common panel test report IDs (less standardized than battery test)
  uint8_t test_report_ids[] = {0x79, 0x0c, 0x1f, 0x15};

  for (size_t i = 0; i < sizeof(test_report_ids); i++)
  {
    uint8_t report_id = test_report_ids[i];
    uint8_t test_data[2] = {report_id, 1}; // Command value 1 = Start test

    ESP_LOGD(GEN_TAG, "Trying UPS test with report ID 0x%02X", report_id);
    esp_err_t ret = parent_->hid_set_report(0x03, report_id, test_data, sizeof(test_data), parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(GEN_TAG, "Generic UPS test command sent with report ID 0x%02X", report_id);
      return true;
    }
    else
    {
      ESP_LOGD(GEN_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }

  ESP_LOGW(GEN_TAG, "Failed to send generic UPS test with all tried report IDs");
  return false;
}

bool GenericHidProtocol::stop_ups_test()
{
  ESP_LOGI(GEN_TAG, "Stopping Generic HID UPS test");

  // Try common panel test report IDs
  uint8_t test_report_ids[] = {0x79, 0x0c, 0x1f, 0x15};

  for (size_t i = 0; i < sizeof(test_report_ids); i++)
  {
    uint8_t report_id = test_report_ids[i];
    uint8_t test_data[2] = {report_id, 0}; // Command value 0 = Stop test

    ESP_LOGD(GEN_TAG, "Trying UPS test stop with report ID 0x%02X", report_id);
    esp_err_t ret = parent_->hid_set_report(0x03, report_id, test_data, sizeof(test_data), parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(GEN_TAG, "Generic UPS test stop command sent with report ID 0x%02X", report_id);
      return true;
    }
    else
    {
      ESP_LOGD(GEN_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }

  ESP_LOGW(GEN_TAG, "Failed to send generic UPS test stop with all tried report IDs");
  return false;
}

void GenericHidProtocol::read_frequency_data(UpsData &data)
{
  // Initialize frequency to NaN
  data.power.frequency = NAN;

  // Try to read frequency from common HID report IDs used across different vendors
  // Generic protocol attempts broader range of report IDs

  const std::vector<uint8_t> frequency_report_ids = {
      HID_USAGE_POW_FREQUENCY, // 0x32 - Standard HID frequency usage
      HID_USAGE_POW_VOLTAGE,   // 0x30 - Input measurements (may include frequency)
      HID_USAGE_POW_CURRENT,   // 0x31 - Output measurements (may include frequency)
      HID_USAGE_POW_OUTPUT,    // 0x1C - Output collection
      HID_USAGE_POW_INPUT,     // 0x1A - Input collection
  };

  uint8_t buffer[limits::MAX_HID_REPORT_SIZE];
  size_t buffer_len;

  for (uint8_t report_id : frequency_report_ids)
  {
    if (read_report(report_id, buffer, buffer_len))
    {
      float frequency_value = parse_frequency_from_report(buffer, buffer_len);
      if (!std::isnan(frequency_value))
      {
        data.power.frequency = frequency_value;
        ESP_LOGD(GEN_TAG, "Found frequency %.1f Hz in report 0x%02X", frequency_value, report_id);
        return;
      }
    }
  }

  ESP_LOGV(GEN_TAG, "Frequency data not available from any HID report");
}

float GenericHidProtocol::parse_frequency_from_report(uint8_t *data, size_t len)
{
  if (len < 2)
  {
    return NAN;
  }

  // Try different byte positions and formats commonly used for frequency across vendors
  // Generic protocol uses broader heuristics than vendor-specific protocols

  // Method 1: Single byte at position 1 (simple frequency reports)
  if (len >= 2)
  {
    uint8_t freq_byte = data[1];
    if (freq_byte >= static_cast<uint8_t>(FREQUENCY_MIN_VALID) && freq_byte <= static_cast<uint8_t>(FREQUENCY_MAX_VALID))
    {
      ESP_LOGD(GEN_TAG, "Found frequency %d Hz (single byte)", freq_byte);
      return static_cast<float>(freq_byte);
    }
  }

  // Method 2: Check all byte positions for valid frequency values
  for (size_t i = 1; i < len; i++)
  {
    uint8_t freq_byte = data[i];
    if ((freq_byte == 50 || freq_byte == 60) && freq_byte <= static_cast<uint8_t>(FREQUENCY_MAX_VALID))
    {
      ESP_LOGD(GEN_TAG, "Found standard frequency %d Hz at byte %zu", freq_byte, i);
      return static_cast<float>(freq_byte);
    }
  }

  // Method 3: 16-bit little-endian values
  for (size_t i = 1; i <= len - 2; i++)
  {
    uint16_t freq_word = data[i] | (data[i + 1] << 8);
    if (freq_word >= static_cast<uint16_t>(FREQUENCY_MIN_VALID) && freq_word <= static_cast<uint16_t>(FREQUENCY_MAX_VALID))
    {
      ESP_LOGD(GEN_TAG, "Found frequency %d Hz (16-bit LE) at bytes %zu-%zu", freq_word, i, i + 1);
      return static_cast<float>(freq_word);
    }
  }

  // Method 4: 16-bit big-endian values
  for (size_t i = 1; i <= len - 2; i++)
  {
    uint16_t freq_word = (data[i] << 8) | data[i + 1];
    if (freq_word >= static_cast<uint16_t>(FREQUENCY_MIN_VALID) && freq_word <= static_cast<uint16_t>(FREQUENCY_MAX_VALID))
    {
      ESP_LOGD(GEN_TAG, "Found frequency %d Hz (16-bit BE) at bytes %zu-%zu", freq_word, i, i + 1);
      return static_cast<float>(freq_word);
    }
  }

  // Method 5: Scaled frequencies (0.1x factor common in some devices)
  for (size_t i = 1; i <= len - 2; i++)
  {
    uint16_t freq_scaled = data[i] | (data[i + 1] << 8);
    float freq_value = static_cast<float>(freq_scaled) / 10.0f;
    if (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID)
    {
      ESP_LOGD(GEN_TAG, "Found scaled frequency %.1f Hz (0.1x) at bytes %zu-%zu", freq_value, i, i + 1);
      return freq_value;
    }
  }

  // Method 6: Check for hundreds scaling (0.01x factor)
  for (size_t i = 1; i <= len - 2; i++)
  {
    uint16_t freq_scaled = data[i] | (data[i + 1] << 8);
    float freq_value = static_cast<float>(freq_scaled) / 100.0f;
    if (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID)
    {
      ESP_LOGD(GEN_TAG, "Found scaled frequency %.1f Hz (0.01x) at bytes %zu-%zu", freq_value, i, i + 1);
      return freq_value;
    }
  }

  return NAN;
}

// Delay configuration methods
bool GenericHidProtocol::set_shutdown_delay(int seconds)
{
  ESP_LOGI(TAG, "Setting shutdown delay to %d seconds (Generic HID)", seconds);

  // Validate range (0-7200 seconds = 0-2 hours)
  if (seconds < 0 || seconds > 7200)
  {
    ESP_LOGW(TAG, "Shutdown delay %d seconds out of range (0-7200)", seconds);
    return false;
  }

  // Try common report IDs for delay configuration
  // Different vendors use different report IDs, so we'll try the most common ones
  const std::vector<uint8_t> delay_report_ids = {
      HID_USAGE_POW_DELAY_BEFORE_SHUTDOWN, // Standard HID usage
  };

  bool success = false;
  for (uint8_t report_id : delay_report_ids)
  {
    uint8_t delay_data[2];
    delay_data[0] = seconds & 0xFF;        // Low byte
    delay_data[1] = (seconds >> 8) & 0xFF; // High byte

    ESP_LOGD(TAG, "Trying shutdown delay on report 0x%02X: %d seconds", report_id, seconds);

    esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, report_id,
                                            delay_data, 2, parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(TAG, "Shutdown delay set successfully via report 0x%02X", report_id);
      success = true;
      break;
    }
  }

  if (!success)
  {
    ESP_LOGW(TAG, "Failed to set shutdown delay - no compatible report found");
  }

  return success;
}

bool GenericHidProtocol::set_start_delay(int seconds)
{
  ESP_LOGI(TAG, "Setting start delay to %d seconds (Generic HID)", seconds);

  // Validate range (0-7200 seconds = 0-2 hours)
  if (seconds < 0 || seconds > 7200)
  {
    ESP_LOGW(TAG, "Start delay %d seconds out of range (0-7200)", seconds);
    return false;
  }

  // Try common report IDs for start delay configuration
  const std::vector<uint8_t> delay_report_ids = {
      HID_USAGE_POW_DELAY_BEFORE_STARTUP, // Standard HID usage
  };

  bool success = false;
  for (uint8_t report_id : delay_report_ids)
  {
    uint8_t delay_data[2];
    delay_data[0] = seconds & 0xFF;        // Low byte
    delay_data[1] = (seconds >> 8) & 0xFF; // High byte

    ESP_LOGD(TAG, "Trying start delay on report 0x%02X: %d seconds", report_id, seconds);

    esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, report_id,
                                            delay_data, 2, parent_->get_protocol_timeout());

    if (ret == ESP_OK)
    {
      ESP_LOGI(TAG, "Start delay set successfully via report 0x%02X", report_id);
      success = true;
      break;
    }
  }

  if (!success)
  {
    ESP_LOGW(TAG, "Failed to set start delay - no compatible report found");
  }

  return success;
}

bool GenericHidProtocol::set_reboot_delay(int seconds)
{
  ESP_LOGI(TAG, "Setting reboot delay to %d seconds (Generic HID)", seconds);

  // For generic HID, reboot typically involves setting both shutdown and start delays
  bool shutdown_ok = set_shutdown_delay(seconds);
  bool start_ok = set_start_delay(seconds);

  if (shutdown_ok || start_ok)
  {
    ESP_LOGI(TAG, "Reboot delay partially set to %d seconds", seconds);
    return true; // Return true if at least one succeeded
  }
  else
  {
    ESP_LOGW(TAG, "Failed to set any reboot delay");
    return false;
  }
}

// Read delay configuration values from UPS
void GenericHidProtocol::read_delay_configuration(UpsData &data)
{
  // Initialize delays to -1 (not available)
  data.config.delay_shutdown = -1;
  data.config.delay_start = -1;
  data.config.delay_reboot = -1;

  uint8_t buffer[limits::MAX_HID_REPORT_SIZE];
  size_t buffer_len;

  // Common delay report IDs based on HID Power Device spec
  const struct
  {
    uint8_t report_id;
    const char *name;
    int16_t *target;
  } delay_reports[] = {
      {HID_USAGE_POW_DELAY_BEFORE_SHUTDOWN, "shutdown", &data.config.delay_shutdown}, // 0x57
      {HID_USAGE_POW_DELAY_BEFORE_STARTUP, "start", &data.config.delay_start},        // 0x56
      {HID_USAGE_POW_DELAY_BEFORE_REBOOT, "reboot", &data.config.delay_reboot},       // 0x55
  };

  for (const auto &delay : delay_reports)
  {
    buffer_len = sizeof(buffer);
    if (read_report(delay.report_id, buffer, buffer_len) && buffer_len >= 2)
    {
      // Try different parsing methods
      int value = -1;

      // Method 1: Single byte value
      if (buffer_len >= 2 && buffer[1] > 0 && buffer[1] < 255)
      {
        value = buffer[1];
      }

      // Method 2: 16-bit little-endian at bytes 1-2
      if (buffer_len >= 3)
      {
        uint16_t value_16 = buffer[1] | (buffer[2] << 8);
        if (value_16 > 0 && value_16 < 7200)
        { // Max 2 hours
          value = value_16;
        }
      }

      // Method 3: 16-bit little-endian at bytes 0-1 (for reports without ID byte)
      if (value == -1 && buffer_len >= 2)
      {
        uint16_t value_16 = buffer[0] | (buffer[1] << 8);
        if (value_16 > 0 && value_16 < 7200)
        {
          value = value_16;
        }
      }

      if (value > 0)
      {
        *delay.target = value;
        ESP_LOGD(GEN_TAG, "Found %s delay: %d seconds (report 0x%02X)", delay.name, value, delay.report_id);
      }
    }
  }

  // Log results
  if (data.config.delay_shutdown > 0 || data.config.delay_start > 0 || data.config.delay_reboot > 0)
  {
    ESP_LOGD(GEN_TAG, "Delay configuration - Shutdown: %ds, Start: %ds, Reboot: %ds",
             data.config.delay_shutdown, data.config.delay_start, data.config.delay_reboot);
  }
  else
  {
    ESP_LOGV(GEN_TAG, "Delay configuration not available from HID reports");
  }
}

// Read load percentage from UPS using multiple report IDs and validation
void GenericHidProtocol::read_load_percentage(UpsData &data)
{
  uint8_t buffer[limits::MAX_HID_REPORT_SIZE];
  size_t buffer_len;

  // Common load percentage report IDs based on HID Power Device spec and vendor analysis
  const struct
  {
    uint8_t report_id;
    const char *name;
    uint8_t byte_offset;
  } load_reports[] = {
      {HID_USAGE_POW_PERCENT_LOAD, "HID standard", 1},     // 0x35 - Standard HID Power Device
      {HID_USAGE_POW_CONFIG_PERCENT_LOAD, "HID config", 1} // 0x45 - Configuration value
  };

  for (const auto &load_report : load_reports)
  {
    buffer_len = sizeof(buffer);
    if (read_report(load_report.report_id, buffer, buffer_len) &&
        buffer_len > load_report.byte_offset)
    {

      uint8_t load_raw = buffer[load_report.byte_offset];

      // Validate against invalid values
      if (load_raw == 0xFF || load_raw == 0x00)
      {
        ESP_LOGV(GEN_TAG, "Invalid load value 0x%02X in report 0x%02X - ignoring",
                 load_raw, load_report.report_id);
        continue;
      }

      float load_percent = NAN;

      // Standard percentage (0-100)
      if (load_raw <= 100)
      {
        load_percent = static_cast<float>(load_raw);
        ESP_LOGD(GEN_TAG, "Load: %.0f%% (%s report 0x%02X, byte %d)",
                 load_percent, load_report.name, load_report.report_id, load_report.byte_offset);
      }
      // Alternative scale (0-200 mapped to 0-100)
      else if (load_raw <= battery::ALTERNATIVE_PERCENTAGE_SCALE)
      {
        load_percent = static_cast<float>(load_raw) * battery::MAX_LEVEL_PERCENT / battery::ALTERNATIVE_PERCENTAGE_SCALE;

        // Validate scaled result is reasonable
        if (load_percent <= battery::MAX_LEVEL_PERCENT)
        {
          ESP_LOGD(GEN_TAG, "Load: %.1f%% (scaled from %d on %s report 0x%02X)",
                   load_percent, load_raw, load_report.name, load_report.report_id);
        }
        else
        {
          ESP_LOGV(GEN_TAG, "Scaled load result %.1f%% exceeds maximum - ignoring", load_percent);
          continue;
        }
      }
      else
      {
        ESP_LOGV(GEN_TAG, "Load value %d out of valid range in report 0x%02X",
                 load_raw, load_report.report_id);
        continue;
      }

      // Set the valid load percentage and return
      if (!std::isnan(load_percent))
      {
        data.power.load_percent = load_percent;
        return;
      }
    }
  }

  // Try 16-bit load values in some reports
  for (const auto &load_report : load_reports)
  {
    buffer_len = sizeof(buffer);
    if (read_report(load_report.report_id, buffer, buffer_len) && buffer_len >= 3)
    {
      // Try 16-bit little-endian at bytes 1-2
      uint16_t load_16 = buffer[1] | (buffer[2] << 8);

      if (load_16 > 0 && load_16 <= 100)
      {
        data.power.load_percent = static_cast<float>(load_16);
        ESP_LOGD(GEN_TAG, "Load: %.0f%% (16-bit from %s report 0x%02X)",
                 data.power.load_percent, load_report.name, load_report.report_id);
        return;
      }
      else if (load_16 <= battery::ALTERNATIVE_PERCENTAGE_SCALE)
      {
        float load_percent = static_cast<float>(load_16) * battery::MAX_LEVEL_PERCENT / battery::ALTERNATIVE_PERCENTAGE_SCALE;
        if (load_percent <= battery::MAX_LEVEL_PERCENT)
        {
          data.power.load_percent = load_percent;
          ESP_LOGD(GEN_TAG, "Load: %.1f%% (16-bit scaled from %d on %s report 0x%02X)",
                   load_percent, load_16, load_report.name, load_report.report_id);
          return;
        }
      }
    }
  }

  ESP_LOGV(GEN_TAG, "Load percentage not available from any HID reports");
}

// Read beeper status from UPS
void GenericHidProtocol::read_beeper_status(UpsData &data)
{
  uint8_t buffer[limits::MAX_HID_REPORT_SIZE];
  size_t buffer_len;

  // Common beeper/audible alarm report IDs
  const uint8_t beeper_report_ids[] = {
      HID_USAGE_POW_AUDIBLE_ALARM_CONTROL // 0x5A - Standard HID
  };

  for (uint8_t report_id : beeper_report_ids)
  {
    buffer_len = sizeof(buffer);
    if (read_report(report_id, buffer, buffer_len) && buffer_len >= 2)
    {
      // Try to parse beeper status
      uint8_t status_byte = buffer[1];

      // Common beeper status values
      if (status_byte == 0x01 || status_byte == beeper::CONTROL_DISABLE)
      {
        data.config.beeper_status = "disabled";
        ESP_LOGD(GEN_TAG, "Beeper status: disabled (report 0x%02X, value 0x%02X)", report_id, status_byte);
        return;
      }
      else if (status_byte == 0x02 || status_byte == beeper::CONTROL_ENABLE)
      {
        data.config.beeper_status = "enabled";
        ESP_LOGD(GEN_TAG, "Beeper status: enabled (report 0x%02X, value 0x%02X)", report_id, status_byte);
        return;
      }
      else if (status_byte == 0x03 || status_byte == beeper::CONTROL_MUTE)
      {
        data.config.beeper_status = "muted";
        ESP_LOGD(GEN_TAG, "Beeper status: muted (report 0x%02X, value 0x%02X)", report_id, status_byte);
        return;
      }

      // Try bit interpretation (some devices use bit flags)
      if (report_id == 0x0C && buffer_len >= 5)
      {
        // CyberPower might include beeper status in power summary report
        // Check byte 4 or 5 for beeper status
        if (buffer_len > 4)
        {
          uint8_t beeper_byte = buffer[4];
          if (beeper_byte & 0x01)
          {
            data.config.beeper_status = "enabled";
            ESP_LOGD(GEN_TAG, "Beeper status: enabled (CyberPower power summary bit)");
            return;
          }
          else if (beeper_byte == 0x00)
          {
            data.config.beeper_status = "disabled";
            ESP_LOGD(GEN_TAG, "Beeper status: disabled (CyberPower power summary bit)");
            return;
          }
        }
      }
    }
  }

  // If we couldn't determine beeper status, leave it as unknown
  ESP_LOGV(GEN_TAG, "Beeper status not available from HID reports");
}

}  // namespace ups_hid
}  // namespace esphome

// Protocol Factory Self-Registration
#include "protocol_factory.h"

namespace esphome {
namespace ups_hid {

// Creator function for Generic protocol
std::unique_ptr<UpsProtocolBase> create_generic_protocol(UpsHidComponent* parent) {
    return std::make_unique<GenericHidProtocol>(parent);
}

} // namespace ups_hid
} // namespace esphome

// Register Generic protocol as fallback for all unknown vendors
REGISTER_UPS_FALLBACK_PROTOCOL(generic_hid_protocol, esphome::ups_hid::create_generic_protocol, "Generic HID Protocol", "Universal HID protocol fallback for unknown UPS vendors with basic monitoring capabilities", 10);

namespace esphome {
namespace ups_hid {
// See protocol_generic.h for why this exists: it gives the linker a real reason
// to keep this translation unit (and therefore the static registrar above) when
// building with --gc-sections.
void ensure_generic_protocol_linked() {}
}  // namespace ups_hid
}  // namespace esphome