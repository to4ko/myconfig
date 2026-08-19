#include "protocol_apc.h"
#include "constants_hid.h"
#include "constants_ups.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include <cstring>
#include <regex>
#include <algorithm>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/portmacro.h"
#include "esp_err.h"

namespace esphome {
namespace ups_hid {

static const char *const APC_HID_TAG = "ups_hid.apc_hid";

// APC HID Usage Pages and Usage IDs (based on NUT project research)
static const uint16_t APC_USAGE_PAGE_UPS = 0x84;
static const uint16_t APC_USAGE_PAGE_BATTERY = 0x85;
static const uint16_t APC_USAGE_PAGE_POWER = 0x80;

// HID Report IDs used by APC UPS devices (based on working ESP32 NUT server)
static const uint8_t APC_REPORT_ID_STATUS = 0x01;    // UPS status flags
static const uint8_t APC_REPORT_ID_BATTERY = 0x06;   // Battery level and runtime  
static const uint8_t APC_REPORT_ID_LOAD = 0x07;      // UPS load information
static const uint8_t APC_REPORT_ID_VOLTAGE = 0x0e;   // Input/output voltage
static const uint8_t APC_REPORT_ID_BEEPER = 0x1f;    // Beeper control

// Additional APC HID Reports for device information (based on NUT apc-hid.c)
static const uint8_t APC_REPORT_ID_DEVICE_INFO = 0x03;     // Device information
static const uint8_t APC_REPORT_ID_FIRMWARE = 0x04;       // Firmware version
static const uint8_t APC_REPORT_ID_AUDIBLE_ALARM = 0x18;  // Audible alarm control (beeper)
static const uint8_t APC_REPORT_ID_SENSITIVITY = 0x35;    // Input sensitivity (APCSensitivity)

// Power and status report IDs
static const uint8_t APC_REPORT_ID_POWER_SUMMARY = 0x0C;   // PowerSummary.RemainingCapacity + RunTimeToEmpty
static const uint8_t APC_REPORT_ID_PRESENT_STATUS = 0x16;  // PowerSummary.PresentStatus bitmap
static const uint8_t APC_REPORT_ID_INPUT_VOLTAGE = 0x31;   // UPS.Input.Voltage
static const uint8_t APC_REPORT_ID_LOAD_PERCENT = 0x50;    // UPS.PowerConverter.PercentLoad  
static const uint8_t APC_REPORT_ID_OUTPUT_VOLTAGE = 0x09;  // PowerSummary.Voltage (legacy)
static const uint8_t APC_REPORT_ID_FREQUENCY = 0x0D;       // Frequency information

// Extended configuration report IDs
static const uint8_t APC_REPORT_ID_BATTERY_RUNTIME_LOW = 0x24; // Battery runtime low threshold
static const uint8_t APC_REPORT_ID_BATTERY_VOLTAGE_NOMINAL = 0x25; // Battery voltage nominal
static const uint8_t APC_REPORT_ID_BATTERY_VOLTAGE = 0x26;  // Battery voltage actual
static const uint8_t APC_REPORT_ID_INPUT_VOLTAGE_NOMINAL = 0x30; // Input voltage nominal  
static const uint8_t APC_REPORT_ID_DELAY_REBOOT = 0x40;    // Delay before reboot
static const uint8_t APC_REPORT_ID_DELAY_SHUTDOWN = 0x41;  // Delay before shutdown
static const uint8_t APC_REPORT_ID_TEST_RESULT = 0x52;     // Test result status
static const uint8_t APC_REPORT_ID_AUDIBLE_BEEPER = 0x78;  // Alternative beeper control

// Additional report IDs found in code
// Note: Serial number report ID moved to shared constant usb::REPORT_ID_SERIAL_NUMBER
static const uint8_t APC_REPORT_ID_MFR_DATE_UPS = 0x07;    // UPS manufacture date
static const uint8_t APC_REPORT_ID_MFR_DATE_BATTERY = 0x20; // Battery manufacture date  
// Note: Battery chemistry report ID moved to shared constant battery_chemistry::REPORT_ID
static const uint8_t APC_REPORT_ID_CHARGE_WARNING = 0x0F;  // Battery charge warning threshold
static const uint8_t APC_REPORT_ID_CHARGE_LOW = 0x11;      // Battery charge low threshold
static const uint8_t APC_REPORT_ID_INPUT_TRANSFER_LOW = 0x32;  // Input low voltage transfer point
static const uint8_t APC_REPORT_ID_INPUT_TRANSFER_HIGH = 0x33; // Input high voltage transfer point
static const uint8_t APC_REPORT_ID_PANEL_TEST = 0x79;      // Panel/UPS test control
static const uint8_t APC_REPORT_ID_BATTERY_TEST = 0x52;    // Battery test control (same as test result)

// Status bit masks
static const uint8_t APC_STATUS_AC_PRESENT = 0x01;        // Bit 0: AC present
static const uint8_t APC_STATUS_CHARGING = 0x04;          // Bit 2: Charging
static const uint8_t APC_STATUS_DISCHARGING = 0x10;       // Bit 4: Discharging  
static const uint8_t APC_STATUS_GOOD = 0x20;              // Bit 5: Battery good
static const uint8_t APC_STATUS_INTERNAL_FAILURE = 0x40;  // Bit 6: Internal failure
static const uint8_t APC_STATUS_NEED_REPLACEMENT = 0x80;  // Bit 7: Need replacement

// Present status bit masks  
static const uint8_t APC_PRESENT_CHARGING = 0x01;         // Bit 0: Charging
static const uint8_t APC_PRESENT_DISCHARGING = 0x02;      // Bit 1: Discharging
static const uint8_t APC_PRESENT_AC_PRESENT = 0x04;       // Bit 2: AC present
static const uint8_t APC_PRESENT_BATTERY_PRESENT = 0x08;  // Bit 3: Battery present
static const uint8_t APC_PRESENT_BELOW_CAPACITY = 0x10;   // Bit 4: Below capacity
static const uint8_t APC_PRESENT_SHUTDOWN_IMMINENT = 0x20; // Bit 5: Shutdown imminent
static const uint8_t APC_PRESENT_TIME_LIMIT_EXPIRED = 0x40; // Bit 6: Time limit expired
static const uint8_t APC_PRESENT_NEED_REPLACEMENT = 0x80;   // Bit 7: Need replacement
static const uint8_t APC_PRESENT_OVERLOAD = 0x01;          // Bit 0 of second byte: Overload

// APC-specific date conversion (hex-as-decimal format)
// Currently unused (kept for future date-report parsing); silences -Wunused-function.
[[maybe_unused]] static std::string convert_apc_date(uint32_t apc_date) {
  if (apc_date == 0) return status::UNKNOWN;
  
  // APC uses hex-as-decimal format, e.g., 0x102202 = 10/22/02
  uint8_t month = (apc_date >> 16) & 0xFF;
  uint8_t day = (apc_date >> 8) & 0xFF;
  uint8_t year = apc_date & 0xFF;
  
  // Convert 2-digit year to 4-digit (Y2K handling)
  uint16_t full_year = (year <= 69) ? (2000 + year) : (1900 + year);
  
  char date_str[16];
  snprintf(date_str, sizeof(date_str), "%02d/%02d/%04d", month, day, full_year);
  return std::string(date_str);
}

// APC HID Protocol implementation
ApcHidProtocol::ApcHidProtocol(UpsHidComponent *parent) : UpsProtocolBase(parent) {}

bool ApcHidProtocol::detect() {
  ESP_LOGD(APC_HID_TAG, "Detecting APC HID Protocol...");
  
  // Check device connection status first
  if (!parent_->is_device_connected()) {
    ESP_LOGD(APC_HID_TAG, "Device not connected, skipping protocol detection");
    return false;
  }
  
  // Give device time to initialize after connection
  vTaskDelay(pdMS_TO_TICKS(timing::USB_INITIALIZATION_DELAY_MS));
  
  // Try key report IDs based on NUT analysis - these are the critical ones
  const uint8_t test_report_ids[] = {
    APC_REPORT_ID_POWER_SUMMARY,   // CRITICAL: PowerSummary.RemainingCapacity + RunTimeToEmpty (NUT primary data)
    APC_REPORT_ID_PRESENT_STATUS,  // CRITICAL: PowerSummary.PresentStatus bitmap (status flags) 
    APC_REPORT_ID_BATTERY,         // PowerSummary.APCStatusFlag (basic status byte)
    APC_REPORT_ID_STATUS,          // Legacy status check
    APC_REPORT_ID_OUTPUT_VOLTAGE   // PowerSummary.Voltage
  };
  
  HidReport test_report;
  
  for (uint8_t report_id : test_report_ids) {
    // Check device connection before each report attempt
    if (!parent_->is_device_connected()) {
      ESP_LOGD(APC_HID_TAG, "Device disconnected during protocol detection");
      return false;
    }
    
    ESP_LOGD(APC_HID_TAG, "Testing report ID 0x%02X...", report_id);
    
    if (read_hid_report(report_id, test_report)) {
      ESP_LOGI(APC_HID_TAG, "SUCCESS: APC HID Protocol detected with report ID 0x%02X (%zu bytes)", 
               report_id, test_report.data.size());
      return true;
    }
    
    // Small delay between attempts
    vTaskDelay(pdMS_TO_TICKS(timing::REPORT_RETRY_DELAY_MS));
  }
  
  ESP_LOGD(APC_HID_TAG, "APC HID Protocol detection failed - no reports responded");
  return false;
}

bool ApcHidProtocol::initialize() {
  ESP_LOGD(APC_HID_TAG, "Initializing APC HID Protocol...");
  
  // Initialize HID communication
  if (!init_hid_communication()) {
    ESP_LOGE(APC_HID_TAG, "Failed to initialize HID communication");
    return false;
  }
  
  // Read basic device information
  read_device_info();
  
  ESP_LOGI(APC_HID_TAG, "APC HID Protocol initialized successfully");
  return true;
}

bool ApcHidProtocol::read_data(UpsData &data) {
  ESP_LOGV(APC_HID_TAG, "Reading APC HID UPS data...");
  
  bool success = false;
  
  // CRITICAL FIX: Read NUT-compatible reports in the correct order first
  // Device info will be read after successful HID communication
  
  // 1. Read PowerSummary report (MOST IMPORTANT - battery % + runtime)
  HidReport power_summary_report;
  if (read_hid_report(APC_REPORT_ID_POWER_SUMMARY, power_summary_report)) {
    parse_power_summary_report(power_summary_report, data);
    success = true;
  } else {
    ESP_LOGV(APC_HID_TAG, "Failed to read PowerSummary report");
  }
  
  // 2. Read PresentStatus report (status bitmap - AC, charging, discharging, etc.)
  HidReport present_status_report;
  if (read_hid_report(APC_REPORT_ID_PRESENT_STATUS, present_status_report)) {
    parse_present_status_report(present_status_report, data);
    success = true;
  } else {
    ESP_LOGV(APC_HID_TAG, "Failed to read PresentStatus report");
  }
  
  // 3. Read APCStatusFlag report (legacy status byte)
  HidReport apc_status_report;
  if (read_hid_report(APC_REPORT_ID_BATTERY, apc_status_report)) {
    parse_apc_status_report(apc_status_report, data);
    success = true;
  } else {
    ESP_LOGV(APC_HID_TAG, "Failed to read APCStatusFlag report");
  }
  
  // 4. Read input voltage report (NUT: UPS.Input.Voltage) 
  HidReport input_voltage_report;
  if (read_hid_report(APC_REPORT_ID_INPUT_VOLTAGE, input_voltage_report)) {
    parse_input_voltage_report(input_voltage_report, data);
    success = true;
  } else {
    ESP_LOGV(APC_HID_TAG, "Failed to read input voltage report");
  }
  
  // 5. Read load percentage report (NUT: UPS.PowerConverter.PercentLoad)
  HidReport load_report;
  if (read_hid_report(APC_REPORT_ID_LOAD_PERCENT, load_report)) {
    parse_load_report(load_report, data);
    success = true;
  } else {
    ESP_LOGV(APC_HID_TAG, "Failed to read load report");
  }
  
  // 6. Read output voltage report (legacy voltage reading)
  HidReport voltage_report;
  if (read_hid_report(APC_REPORT_ID_OUTPUT_VOLTAGE, voltage_report)) {
    parse_voltage_report(voltage_report, data);
    success = true;
  } else {
    ESP_LOGV(APC_HID_TAG, "Failed to read voltage report");
  }
  
  // Set frequency to NaN - not available in debug logs for this APC model
  // Try to read frequency from HID reports
  read_frequency_data(data);
  ESP_LOGV(APC_HID_TAG, "Frequency: Not available on this UPS model");
  
  // TIMING FIX: Only read USB string descriptors after successful HID communication
  // This ensures the device is ready and responsive before attempting descriptor access
  if (success) {
    ESP_LOGD(APC_HID_TAG, "APC HID data read successful, now reading device info...");
    
    // Read manufacturer from USB Manufacturer string descriptor (index 3)
    // NUT shows: UPS.PowerSummary.iManufacturer, Value: 3 → Manufacturer: "APC"
    std::string manufacturer_string;
    esp_err_t mfr_ret = parent_->usb_get_string_descriptor(3, manufacturer_string);
    
    if (mfr_ret == ESP_OK && !manufacturer_string.empty()) {
      data.device.manufacturer = manufacturer_string;
      ESP_LOGI(APC_HID_TAG, "Successfully read manufacturer from USB descriptor: \"%s\"", data.device.manufacturer.c_str());
    } else {
      data.device.manufacturer.clear();  // Set to unset state instead of hardcoded fallback
      ESP_LOGW(APC_HID_TAG, "Failed to read USB Manufacturer descriptor: %s, leaving unset", esp_err_to_name(mfr_ret));
    }
    
    // Read model from USB Product string descriptor (index 1)
    // NUT shows: Product: "Back-UPS ES 700G" but need to parse out firmware info
    std::string product_string;
    esp_err_t prod_ret = parent_->usb_get_string_descriptor(1, product_string);
    
    if (prod_ret == ESP_OK && !product_string.empty()) {
      // Parse out just the model name, removing firmware info like "FW:841.H1 .D USB FW:H1"
      std::string model_name = product_string;
      size_t fw_pos = model_name.find(" FW:");
      if (fw_pos != std::string::npos) {
        model_name = model_name.substr(0, fw_pos);
      }
      data.device.model = model_name;
      ESP_LOGI(APC_HID_TAG, "Successfully read APC model from USB Product descriptor: \"%s\"", data.device.model.c_str());
      
      // Detect and set nominal power rating based on model name
      detect_nominal_power_rating(data.device.model, data);
    } else {
      data.device.model.clear();  // Set to unset state instead of hardcoded fallback
      ESP_LOGW(APC_HID_TAG, "Failed to read USB Product descriptor: %s, leaving model unset", esp_err_to_name(prod_ret));
    }
    
    // Read additional device information (serial, firmware, etc.)
    read_device_information(data);
    
    // Read missing dynamic values identified from NUT analysis
    read_missing_dynamic_values(data);
    
    ESP_LOGV(APC_HID_TAG, "Successfully read UPS data");
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to read any APC HID reports");
    // Leave manufacturer and model unset when HID communication fails
    data.device.manufacturer.clear();
    data.device.model.clear();
  }
  
  // Set default test result
  if (data.test.ups_test_result.empty()) {
    data.test.ups_test_result = test::RESULT_NO_TEST;
  }
  
  return success;
}

bool ApcHidProtocol::init_hid_communication() {
  // Set up HID communication parameters
  // For APC devices, we typically use standard HID interrupt transfers
  return true;
}

bool ApcHidProtocol::read_hid_report(uint8_t report_id, HidReport &report) {
  // Check device connection before any HID communication
  if (!parent_->is_device_connected()) {
    ESP_LOGV(APC_HID_TAG, "Device not connected, skipping HID report 0x%02X", report_id);
    return false;
  }
  
#ifdef USE_ESP32
  uint8_t buffer[64]; // Maximum HID report size
  size_t buffer_len = sizeof(buffer);
  esp_err_t ret;
  
  // CRITICAL FIX: Try Input Report first (HID_REPORT_TYPE_INPUT) - this is what NUT uses for real-time data
  // Based on NUT logs showing PowerSummary fields work with Input Reports
  ESP_LOGV(APC_HID_TAG, "Trying Input report 0x%02X...", report_id);
  ret = parent_->hid_get_report(HID_REPORT_TYPE_INPUT, report_id, buffer, &buffer_len, parent_->get_protocol_timeout());
  if (ret == ESP_OK && buffer_len > 0) {
    report.report_id = report_id;
    report.data.assign(buffer, buffer + buffer_len);
    ESP_LOGD(APC_HID_TAG, "HID Input report 0x%02X: received %zu bytes", report_id, buffer_len);
    log_raw_data(buffer, buffer_len);
    return true;
  }
  
  // Check connection again before trying Feature report
  if (!parent_->is_device_connected()) {
    ESP_LOGV(APC_HID_TAG, "Device disconnected during HID communication for report 0x%02X", report_id);
    return false;
  }
  
  // Fall back to Feature Report (HID_REPORT_TYPE_FEATURE) for static/config data
  buffer_len = sizeof(buffer); // Reset buffer length
  ESP_LOGV(APC_HID_TAG, "Trying Feature report 0x%02X...", report_id);
  ret = parent_->hid_get_report(HID_REPORT_TYPE_FEATURE, report_id, buffer, &buffer_len, parent_->get_protocol_timeout());
  if (ret == ESP_OK && buffer_len > 0) {
    report.report_id = report_id;
    report.data.assign(buffer, buffer + buffer_len);
    ESP_LOGD(APC_HID_TAG, "HID Feature report 0x%02X: received %zu bytes", report_id, buffer_len);
    log_raw_data(buffer, buffer_len);
    return true;
  }
  
  ESP_LOGD(APC_HID_TAG, "Both Input and Feature report 0x%02X failed", report_id);
  return false;
#else
  // Simulation mode - return simulated data
  if (parent_->get_simulation_mode()) {
    return parent_->simulate_hid_get_report(report_id, report);
  }
  ESP_LOGW(APC_HID_TAG, "HID communication not available on this platform");
  return false;
#endif
}

void ApcHidProtocol::log_raw_data(const uint8_t* buffer, size_t buffer_len) {
  if (buffer_len > 0) {
    std::string hex_data;
    for (size_t i = 0; i < buffer_len; i++) {
      char hex_byte[4];
      snprintf(hex_byte, sizeof(hex_byte), "%02X ", buffer[i]);
      hex_data += hex_byte;
    }
    ESP_LOGD(APC_HID_TAG, "Raw data (%zu bytes): %s", buffer_len, hex_data.c_str());
    
    // Detailed byte-by-byte analysis
    for (size_t i = 0; i < buffer_len; i++) {
      ESP_LOGV(APC_HID_TAG, "  Byte[%zu]: 0x%02X (%d decimal)", i, buffer[i], buffer[i]);
    }
  }
}

bool ApcHidProtocol::write_hid_report(const HidReport &report) {
#ifdef USE_ESP32
  // Use HID Feature Report for UPS control commands  
  const uint8_t report_type = HID_REPORT_TYPE_FEATURE; // Feature Report
  
  esp_err_t ret = parent_->hid_set_report(report_type, report.report_id, 
                                          report.data.data(), report.data.size(), parent_->get_protocol_timeout());
  if (ret != ESP_OK) {
    ESP_LOGD(APC_HID_TAG, "HID SET_REPORT failed: %s", esp_err_to_name(ret));
    return false;
  }
  
  ESP_LOGD(APC_HID_TAG, "HID report 0x%02X: sent %zu bytes", report.report_id, report.data.size());
  return true;
#else
  // Simulation mode - return simulated success
  if (parent_->get_simulation_mode()) {
    ESP_LOGD(APC_HID_TAG, "Simulated HID report 0x%02X: sent %zu bytes", report.report_id, report.data.size());
    return true;
  }
  ESP_LOGW(APC_HID_TAG, "HID communication not available on this platform");
  return false;
#endif
}

// ============================================================================
// APC Report Parser - Extracted parsing logic for better organization
// ============================================================================

namespace {

using HidReport = ApcHidProtocol::HidReport;

class ApcReportParser {
public:
  // Status and state parsing
  static void parse_status_report(const HidReport &report, UpsData &data);
  static void parse_present_status_report(const HidReport &report, UpsData &data);
  static void parse_apc_status_report(const HidReport &report, UpsData &data);
  
  // Power and battery parsing
  static void parse_battery_report(const HidReport &report, UpsData &data);
  // Currently unused (superseded by ApcHidProtocol::parse_power_report); kept for reference.
  [[maybe_unused]] static void parse_power_report(const HidReport &report, UpsData &data);
  static void parse_power_summary_report(const HidReport &report, UpsData &data);
  static void parse_voltage_report(const HidReport &report, UpsData &data);
  static void parse_input_voltage_report(const HidReport &report, UpsData &data);
  static void parse_load_report(const HidReport &report, UpsData &data);
  
  // Battery-specific parsing
  static void parse_battery_voltage_nominal_report(const HidReport &report, UpsData &data);
  static void parse_battery_voltage_actual_report(const HidReport &report, UpsData &data);
  static void parse_battery_runtime_low_report(const HidReport &report, UpsData &data);
  static void parse_battery_charge_threshold_report(const HidReport &report, UpsData &data, bool is_low_threshold);
  static void parse_battery_chemistry_report(const HidReport &report, UpsData &data);
  
  // Device information parsing
  static void parse_device_info_report(const HidReport &report);
  static void parse_serial_number_report(const HidReport &report, UpsData &data);
  static void parse_firmware_version_report(const HidReport &report, UpsData &data);
  static void parse_manufacture_date_report(const HidReport &report, UpsData &data, bool is_battery);
  
  // Configuration parsing
  static void parse_input_voltage_nominal_report(const HidReport &report, UpsData &data);
  static void parse_input_transfer_limits_report(const HidReport &report, UpsData &data);
  static void parse_beeper_status_report(const HidReport &report, UpsData &data);
  static void parse_input_sensitivity_report(const HidReport &report, UpsData &data);
  
  // Timer and delay parsing
  static void parse_ups_delay_shutdown_report(const HidReport &report, UpsData &data);
  static void parse_ups_delay_reboot_report(const HidReport &report, UpsData &data);
  
  // Test result parsing
  static void parse_test_result_report(const HidReport &report, UpsData &data);
};

void ApcReportParser::parse_device_info_report(const HidReport &report) {
  // Device info report parsing (implementation needed)
  ESP_LOGD(TAG, "Device info report received");
}

void ApcReportParser::parse_power_summary_report(const HidReport &report, UpsData &data) {
  // PowerSummary report: RemainingCapacity + RunTimeToEmpty
  // CORRECTED: ESP32 data [0C 64 B2 02] - byte 1 is battery %, bytes 2-3 are runtime
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "PowerSummary report too short: %zu bytes", report.data.size());
    return;
  }
  
  // ESP32 data format: [APC_REPORT_ID_POWER_SUMMARY 63 67 02] where 0x63 = 99% battery
  // Battery percentage at byte 1 (NUT offset 0 within report payload)
  data.battery.level = static_cast<float>(report.data[1]);
  ESP_LOGD(APC_HID_TAG, "Raw battery byte: 0x%02X = %d%%", report.data[1], report.data[1]);
  ESP_LOGI(APC_HID_TAG, "PowerSummary: Battery %.0f%%", data.battery.level);
  
  // Runtime at bytes 2-3 (16-bit little-endian, NUT offset 8)
  // CORRECTED: Raw HID value is in seconds (like NUT), convert to minutes for ESPHome
  if (report.data.size() >= 4) {
    uint16_t runtime_raw = report.data[2] | (report.data[3] << 8);
    if (runtime_raw > 0 && runtime_raw < 65535) {
      // Convert seconds to minutes to match ESPHome sensor expectations  
      data.battery.runtime_minutes = static_cast<float>(runtime_raw) / 60.0f;
      ESP_LOGI(APC_HID_TAG, "PowerSummary: Runtime %d seconds (%.1f minutes)", runtime_raw, data.battery.runtime_minutes);
    }
  }
}

void ApcReportParser::parse_present_status_report(const HidReport &report, UpsData &data) {
  // PresentStatus report: PowerSummary.PresentStatus - HID field structure
  // Based on NUT logs showing exact offsets for each 1-bit field:
  // Offset 0: Charging, Offset 1: Discharging, Offset 2: ACPresent, Offset 3: BatteryPresent, etc.
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "PresentStatus report too short: %zu bytes", report.data.size());
    return;
  }
  
  // ESP32 receives packed data, but NUT shows individual bit fields at offsets
  // The HID descriptor defines how these bits are packed into the report
  uint8_t packed_status = report.data[1];
  ESP_LOGD(APC_HID_TAG, "PresentStatus packed data: 0x%02X", packed_status);
  
  // Extract individual status bits based on NUT field offsets
  // NUT shows these are 1-bit fields at specific offsets within the report
  bool charging = (packed_status & APC_PRESENT_CHARGING) != 0;        // Offset 0, Size 1
  bool discharging = (packed_status & APC_PRESENT_DISCHARGING) != 0;     // Offset 1, Size 1
  bool ac_present = (packed_status & APC_PRESENT_AC_PRESENT) != 0;      // Offset 2, Size 1  
  bool battery_present = (packed_status & APC_PRESENT_BATTERY_PRESENT) != 0; // Offset 3, Size 1
  bool below_capacity = (packed_status & APC_PRESENT_BELOW_CAPACITY) != 0;  // Offset 4, Size 1
  bool shutdown_imminent = (packed_status & APC_PRESENT_SHUTDOWN_IMMINENT) != 0; // Offset 5, Size 1
  bool time_limit_expired = (packed_status & APC_PRESENT_TIME_LIMIT_EXPIRED) != 0; // Offset 6, Size 1
  bool need_replacement = (packed_status & APC_PRESENT_NEED_REPLACEMENT) != 0;   // Offset 7, Size 1
  
  // Check for Overload at Offset 8 (second byte if available)
  bool overload = false;
  if (report.data.size() >= 3) {
    uint8_t second_byte = report.data[2];
    overload = (second_byte & APC_PRESENT_OVERLOAD) != 0;  // Offset 8 = bit 0 of second byte
    ESP_LOGD(APC_HID_TAG, "Second status byte: 0x%02X, Overload: %d", second_byte, overload);
  }
  
  // Update power status based on AC presence and discharging
  if (ac_present && !discharging) {
    // Note: Can't access parent_->get_fallback_nominal_voltage() in static method
    // The voltage will be set by the actual voltage reports if available
    data.power.status = status::ONLINE;
  } else {
    data.power.input_voltage = NAN;     // No AC input
    data.power.status = status::ON_BATTERY;
  }
  
  // Update battery status
  if (charging) {
    data.battery.status = battery_status::CHARGING;
  } else if (discharging) {
    data.battery.status = battery_status::DISCHARGING;
  } else {
    data.battery.status = battery_status::NORMAL;
  }
  
  // Handle battery issues
  if (below_capacity || shutdown_imminent) {
    data.battery.charge_low = battery::LOW_THRESHOLD_PERCENT;  // Indicate low battery threshold
    if (shutdown_imminent) {
      data.battery.status += battery_status::SHUTDOWN_IMMINENT_SUFFIX;
    }
  }
  
  if (need_replacement) {
    data.battery.status += battery_status::REPLACE_BATTERY_SUFFIX;
  }
  
  if (!battery_present) {
    data.battery.status = battery_status::NOT_PRESENT;
  }
  
  if (overload) {
    data.power.status += " - Overload";
  }
  
  ESP_LOGI(APC_HID_TAG, "PresentStatus: 0x%02X AC:%d Discharge:%d Charge:%d Battery:%d → Power:\"%s\" Battery:\"%s\"", 
           packed_status, ac_present, discharging, charging, battery_present, 
           data.power.status.c_str(), data.battery.status.c_str());
}

void ApcReportParser::parse_apc_status_report(const HidReport &report, UpsData &data) {
  // APCStatusFlag report: PowerSummary.APCStatusFlag (single byte legacy status)
  // ESP32 data format: [06 XX] where XX is the status value
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "APCStatus report too short: %zu bytes", report.data.size());
    return;
  }
  
  // ESP32 data format: [APC_REPORT_ID_BATTERY 08] where 0x08 = AC present  
  uint8_t apc_status = report.data[1]; // Byte 1 contains the status value
  ESP_LOGD(APC_HID_TAG, "Raw APCStatusFlag byte: 0x%02X", apc_status);
  ESP_LOGI(APC_HID_TAG, "APCStatusFlag: 0x%02X", apc_status);
  
  // Parse APC legacy status values from NUT logs:
  // Value 8 = AC present (UPS online)
  // Value 16 = discharging (UPS on battery) 
  bool apc_ac_present = (apc_status == 8);
  bool apc_discharging = (apc_status == 16);
  
  // Use APCStatusFlag as backup/confirmation for PresentStatus
  // This provides additional validation of the UPS state
  if (apc_ac_present) {
    ESP_LOGD(APC_HID_TAG, "APCStatusFlag confirms: UPS online (AC present)");
  } else if (apc_discharging) {
    ESP_LOGD(APC_HID_TAG, "APCStatusFlag confirms: UPS on battery (discharging)");
  } else {
    ESP_LOGW(APC_HID_TAG, "APCStatusFlag unknown value: 0x%02X", apc_status);
  }
  
  // Don't override PresentStatus data, just log for debugging
  // PresentStatus report is more detailed and authoritative
}

void ApcReportParser::parse_input_voltage_report(const HidReport &report, UpsData &data) {
  // Input voltage report: UPS.Input.Voltage (16-bit value)
  // NUT logs show values like 236V, 232V (AC input voltage)
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Input voltage report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse 16-bit voltage value (little-endian)
  uint16_t voltage_raw = report.data[1] | (report.data[2] << 8);
  data.power.input_voltage = static_cast<float>(voltage_raw);
  
  ESP_LOGI(APC_HID_TAG, "Input voltage: %.1fV", data.power.input_voltage);
}

void ApcReportParser::parse_load_report(const HidReport &report, UpsData &data) {
  // Load report: UPS.PowerConverter.PercentLoad (8-bit percentage)
  // NUT logs show values like 23%, 16% (load percentage)
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Load report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse 8-bit load percentage
  data.power.load_percent = static_cast<float>(report.data[1]);
  
  ESP_LOGI(APC_HID_TAG, "Load percentage: %.0f%%", data.power.load_percent);
}

} // anonymous namespace

// ============================================================================
// APC Protocol Implementation - Now delegates to parser classes
// ============================================================================

void ApcHidProtocol::parse_status_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_status_report(report, data);
}

// Battery report parsing implementation
void ApcReportParser::parse_battery_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Battery report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse battery level based on working ESP32 NUT server implementation
  // APCStatusFlag report: recv[1] = battery charge percentage
  // report.data[0] = report ID (APC_REPORT_ID_BATTERY)  
  // report.data[1] = battery charge level percentage (direct value)
  data.battery.level = static_cast<float>(report.data[1]);
  ESP_LOGI(APC_HID_TAG, "Battery level: %.0f%%", data.battery.level);
  
  // Parse runtime if more bytes available (32-bit little-endian)
  // CORRECTED: Raw HID value is in seconds (like NUT), convert to minutes for ESPHome
  // recv[2] + 256 * recv[3] + 256 * 256 * recv[4] + 256 * 256 * 256 * recv[5]
  if (report.data.size() >= 6) {
    uint32_t runtime_raw = report.data[2] + 
                          (report.data[3] << 8) + 
                          (report.data[4] << 16) + 
                          (report.data[5] << 24);
    if (runtime_raw > 0 && runtime_raw < 65535) { // Sanity check
      // Convert seconds to minutes to match ESPHome sensor expectations
      data.battery.runtime_minutes = static_cast<float>(runtime_raw) / 60.0f;
      ESP_LOGI(APC_HID_TAG, "Runtime: %u seconds (%.1f minutes)", static_cast<unsigned int>(runtime_raw), data.battery.runtime_minutes);
    } else {
      // Set estimate based on battery level if raw value seems invalid
      data.battery.runtime_minutes = data.battery.level * 0.5f; 
      ESP_LOGV(APC_HID_TAG, "Using estimated runtime: %.0f minutes", data.battery.runtime_minutes);
    }
  } else {
    // Set reasonable default if runtime not available
    data.battery.runtime_minutes = data.battery.level * 0.5f; // Rough estimate based on battery level
    ESP_LOGV(APC_HID_TAG, "Using estimated runtime: %.0f minutes", data.battery.runtime_minutes);
  }
}

// Status report parsing implementation
void ApcReportParser::parse_status_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Status report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse APC HID status based on working NUT implementation
  // report.data[0] = report ID (APC_REPORT_ID_STATUS)
  // report.data[1] = status flags byte
  uint8_t status_byte = report.data[1];
  
  ESP_LOGD(APC_HID_TAG, "Status byte: 0x%02X", status_byte);
  
  // Parse status flags based on working NUT server implementation
  bool ac_present = status_byte & APC_STATUS_AC_PRESENT;           // Bit 0: AC present
  bool charging = status_byte & APC_STATUS_CHARGING;             // Bit 2: Charging  
  bool discharging = status_byte & APC_STATUS_DISCHARGING;          // Bit 4: Discharging
  bool good = status_byte & APC_STATUS_GOOD;                 // Bit 5: Battery good
  bool internal_failure = status_byte & APC_STATUS_INTERNAL_FAILURE;     // Bit 6: Internal failure
  bool need_replacement = status_byte & APC_STATUS_NEED_REPLACEMENT;     // Bit 7: Need replacement
  
  // Update power status based on AC presence and discharging
  if (ac_present && !discharging) {
    // Note: Can't access parent_->get_fallback_nominal_voltage() in static method
    // The voltage will be set by the actual voltage reports if available
    data.power.status = status::ONLINE;
  } else {
    data.power.input_voltage = NAN;     // No AC input
    data.power.status = status::ON_BATTERY;
  }
  
  // Update battery status
  if (charging) {
    data.battery.status = battery_status::CHARGING;
  } else if (discharging) {
    data.battery.status = battery_status::DISCHARGING;
  } else {
    data.battery.status = battery_status::NOT_CHARGING;
  }
  
  // Check battery health
  if (!good || internal_failure || need_replacement) {
    if (need_replacement) {
      data.battery.status += battery_status::REPLACE_BATTERY_SUFFIX;
    } else if (internal_failure) {
      data.battery.status += battery_status::INTERNAL_FAILURE_SUFFIX;
    } else {
      data.battery.status += battery_status::CHECK_BATTERY_SUFFIX;
    }
  }
  
  // Check for additional status bytes if available (flexible parsing)
  if (report.data.size() >= 3) {
    uint8_t overload_byte = report.data[2];
    if (overload_byte > 0) {
      data.power.status += " - Overload";
    }
  }
  
  if (report.data.size() >= 4) {
    uint8_t shutdown_byte = report.data[3];
    if (shutdown_byte > 0) {
      data.battery.charge_low = battery::LOW_THRESHOLD_PERCENT;  // Indicate low battery threshold
    }
  }
  
  ESP_LOGI(APC_HID_TAG, "UPS Status - AC:%s, Charging:%s, Discharging:%s, Good:%s, Status:\"%s\"", 
           ac_present ? "Yes" : "No", 
           charging ? "Yes" : "No",
           discharging ? "Yes" : "No",
           good ? "Yes" : "No",
           data.power.status.c_str());
}

// Voltage report parsing implementation
void ApcReportParser::parse_voltage_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Voltage report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse voltage - handle both 2-byte and 3-byte reports
  // report.data[0] = report ID (APC_REPORT_ID_VOLTAGE)
  // report.data[1] = voltage (primary byte)
  uint16_t voltage_raw = report.data[1];
  
  // If we have a second byte, treat it as high byte for 16-bit value
  if (report.data.size() >= 3) {
    voltage_raw |= (report.data[2] << 8);
    ESP_LOGV(APC_HID_TAG, "16-bit voltage: 0x%04X", voltage_raw);
  } else {
    ESP_LOGV(APC_HID_TAG, "8-bit voltage: 0x%02X", voltage_raw);
  }
  
  // This report provides output voltage, apply proper scaling
  // Raw values like 0x0557 (1367) need to be scaled to reasonable voltage
  float voltage_scaled;
  if (voltage_raw > 1000) {
    // Assume raw value needs scaling (e.g., 1367 → 136.7V)
    voltage_scaled = voltage_raw / battery::VOLTAGE_SCALE_FACTOR;
  } else {
    voltage_scaled = static_cast<float>(voltage_raw);
  }
  
  data.power.output_voltage = voltage_scaled;
  
  ESP_LOGI(APC_HID_TAG, "Output voltage: %.1fV", data.power.output_voltage);
}

// Power report parsing implementation
void ApcReportParser::parse_power_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Power report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse load - handle different report sizes
  // report.data[0] = report ID (APC_REPORT_ID_LOAD)
  
  if (report.data.size() >= 7) {
    // Working ESP32 NUT server format: recv[6] = UPS load percentage
    data.power.load_percent = static_cast<float>(report.data[6]);
    ESP_LOGI(APC_HID_TAG, "Load: %.0f%% (from byte 6)", data.power.load_percent);
  } else {
    // Shorter format - try different bytes to find load percentage
    // Current data: 07 39 4B (57, 75 in decimal)
    
    // Method 1: Try byte 1 (0x39 = 57%)
    uint8_t load_candidate1 = report.data[1];
    // Method 2: Try byte 2 (0x4B = 75%)
    uint8_t load_candidate2 = report.data[2];
    
    ESP_LOGI(APC_HID_TAG, "Load candidates - Byte1: %d%%, Byte2: %d%%", 
             load_candidate1, load_candidate2);
    
    // Use the first reasonable value (prefer byte 1 based on previous analysis)
    if (load_candidate1 <= 100) {
      data.power.load_percent = static_cast<float>(load_candidate1);
      ESP_LOGI(APC_HID_TAG, "Load: %.0f%% (from byte 1)", data.power.load_percent);
    } else if (load_candidate2 <= 100) {
      data.power.load_percent = static_cast<float>(load_candidate2);
      ESP_LOGI(APC_HID_TAG, "Load: %.0f%% (from byte 2)", data.power.load_percent);
    } else {
      ESP_LOGW(APC_HID_TAG, "No valid load percentage found");
    }
  }
}

void ApcHidProtocol::parse_battery_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_battery_report(report, data);
}

void ApcHidProtocol::parse_voltage_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_voltage_report(report, data);
}

void ApcHidProtocol::parse_power_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Power report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Parse load - handle different report sizes
  // report.data[0] = report ID (APC_REPORT_ID_LOAD)
  
  if (report.data.size() >= 7) {
    // Working ESP32 NUT server format: recv[6] = UPS load percentage
    data.power.load_percent = static_cast<float>(report.data[6]);
    ESP_LOGI(APC_HID_TAG, "Load: %.0f%% (from byte 6)", data.power.load_percent);
  } else {
    // Shorter format - try different bytes to find load percentage
    // Current data: 07 39 4B (57, 75 in decimal)
    
    // Method 1: Try byte 1 (0x39 = 57%)
    uint8_t load_candidate1 = report.data[1];
    // Method 2: Try byte 2 (0x4B = 75%)
    uint8_t load_candidate2 = report.data[2];
    
    ESP_LOGI(APC_HID_TAG, "Load candidates - Byte1: %d%%, Byte2: %d%%", 
             load_candidate1, load_candidate2);
    
    // Use the first reasonable value (prefer byte 1 based on previous analysis)
    if (load_candidate1 <= 100) {
      data.power.load_percent = static_cast<float>(load_candidate1);
      ESP_LOGI(APC_HID_TAG, "Load: %.0f%% (from byte 1)", data.power.load_percent);
    } else if (load_candidate2 <= 100) {
      data.power.load_percent = static_cast<float>(load_candidate2);
      ESP_LOGI(APC_HID_TAG, "Load: %.0f%% (from byte 2)", data.power.load_percent);
    } else {
      ESP_LOGW(APC_HID_TAG, "No valid load percentage found");
    }
  }
}

void ApcHidProtocol::read_device_info() {
  // Skip reading device info if not connected
  if (!parent_->is_connected()) {
    ESP_LOGD(APC_HID_TAG, "Skipping device info read - device not connected");
    return;
  }
  
  // Read configuration report for device information
  HidReport config_report;
  if (read_hid_report(APC_REPORT_ID_BEEPER, config_report)) {
    parse_device_info_report(config_report);
  }
}

void ApcHidProtocol::parse_device_info_report(const HidReport &report) {
  ApcReportParser::parse_device_info_report(report);
}

// NUT-compatible parser implementations based on real device data analysis
void ApcHidProtocol::parse_power_summary_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_power_summary_report(report, data);
}

void ApcHidProtocol::parse_present_status_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_present_status_report(report, data);
}

void ApcHidProtocol::parse_apc_status_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_apc_status_report(report, data);
}

void ApcHidProtocol::parse_input_voltage_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_input_voltage_report(report, data);
}

void ApcHidProtocol::parse_load_report(const HidReport &report, UpsData &data) {
  ApcReportParser::parse_load_report(report, data);
}

void ApcHidProtocol::read_device_information(UpsData &data) {
  ESP_LOGD(APC_HID_TAG, "Reading APC device information...");
  
  // Try to read USB string descriptors first (most reliable for APC devices)
  // Based on NUT apc_format_serial/apc_format_model implementation
  
  // Read serial number from standard USB HID report (same as CyberPower)
  // NUT debug shows: UPS.PowerSummary.iSerialNumber, ReportID: usb::REPORT_ID_SERIAL_NUMBER, Value: 2
  HidReport serial_report;
  if (read_hid_report(usb::REPORT_ID_SERIAL_NUMBER, serial_report)) {
    parse_serial_number_report(serial_report, data);
  }
  
  // Try reading firmware version
  HidReport firmware_report;
  if (read_hid_report(APC_REPORT_ID_FIRMWARE, firmware_report)) {
    parse_firmware_version_report(firmware_report, data);
  }
  
  // Try reading beeper status
  HidReport beeper_report;
  if (read_hid_report(APC_REPORT_ID_AUDIBLE_ALARM, beeper_report)) {
    parse_beeper_status_report(beeper_report, data);
  }
  
  // Try reading input sensitivity
  HidReport sensitivity_report;
  if (read_hid_report(APC_REPORT_ID_SENSITIVITY, sensitivity_report)) {
    parse_input_sensitivity_report(sensitivity_report, data);
  }
  
  ESP_LOGD(APC_HID_TAG, "Device information reading completed");
}

void ApcHidProtocol::parse_serial_number_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Serial number report too short: %zu bytes", report.data.size());
    return;
  }

  // NUT debug shows: UPS.PowerSummary.iSerialNumber, ReportID: usb::REPORT_ID_SERIAL_NUMBER, Value: 2 
  // This is a USB string descriptor index, not the actual serial number
  uint8_t string_index = report.data[1];
  
  ESP_LOGD(APC_HID_TAG, "Serial number string descriptor index: %d", string_index);
  
  // Use real USB string descriptor reading - this will get the actual APC serial number
  // NUT shows: APC real serial = "5B1738T47814"
  std::string actual_serial;
  esp_err_t ret = parent_->usb_get_string_descriptor(string_index, actual_serial);
  
  if (ret == ESP_OK && !actual_serial.empty()) {
    data.device.serial_number = actual_serial;
    ESP_LOGI(APC_HID_TAG, "Successfully read APC serial number from USB string descriptor %d: \"%s\"", 
             string_index, data.device.serial_number.c_str());
  } else {
    // Fallback if USB string descriptor reading fails
    ESP_LOGW(APC_HID_TAG, "Failed to read USB string descriptor %d: %s", 
             string_index, esp_err_to_name(ret));
    
    // Set to unset state instead of generating fallback ID
    data.device.serial_number.clear();
    ESP_LOGW(APC_HID_TAG, "Leaving serial number unset due to USB string descriptor failure");
  }
}

void ApcHidProtocol::parse_firmware_version_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGV(APC_HID_TAG, "Firmware version report too short: %zu bytes", report.data.size());
    return;
  }
  
  // DYNAMIC FIRMWARE VERSION: Check if report contains a string descriptor index
  // Similar to serial number parsing - some APC devices store firmware info in USB string descriptors
  uint8_t first_byte = report.data[1];
  
  // CRITICAL FIX: Skip manufacturer string descriptor (index 3) which contains "APC"
  // From the log we see that index 3 = "APC" (manufacturer), not firmware
  if (first_byte > 0 && first_byte <= 15 && first_byte != 3) {
    ESP_LOGD(APC_HID_TAG, "Trying firmware as USB string descriptor index: %d", first_byte);
    
    std::string firmware_from_usb;
    esp_err_t ret = parent_->usb_get_string_descriptor(first_byte, firmware_from_usb);
    
    if (ret == ESP_OK && !firmware_from_usb.empty() && 
        firmware_from_usb != "APC" && firmware_from_usb != data.device.manufacturer) {
      // Successfully read firmware from USB string descriptor (not manufacturer)
      data.device.firmware_version = firmware_from_usb;
      
      // Extract auxiliary firmware info (NUT shows ups.firmware.aux: "O4 ")
      // Format: "871.O4 .I" → main="871.O4" aux="O4"
      size_t dot_pos = firmware_from_usb.find('.');
      if (dot_pos != std::string::npos && dot_pos < firmware_from_usb.length() - 1) {
        std::string after_dot = firmware_from_usb.substr(dot_pos + 1);
        size_t space_pos = after_dot.find(' ');
        if (space_pos != std::string::npos) {
          data.device.firmware_aux = after_dot.substr(0, space_pos);
          ESP_LOGI(APC_HID_TAG, "Extracted APC firmware aux: \"%s\"", data.device.firmware_aux.c_str());
        }
      }
      
      ESP_LOGI(APC_HID_TAG, "Successfully read APC firmware from USB string descriptor %d: \"%s\"", 
               first_byte, data.device.firmware_version.c_str());
      return;
    } else {
      ESP_LOGD(APC_HID_TAG, "USB string descriptor %d read failed or contains manufacturer info: %s, trying other methods", 
               first_byte, esp_err_to_name(ret));
    }
  } else if (first_byte == 3) {
    ESP_LOGD(APC_HID_TAG, "Skipping manufacturer string descriptor index 3 for firmware");
  }
  
  // FALLBACK 1 (PRIORITY): Parse firmware from the USB Product string descriptor (index 1)
  // This is the most reliable method for APC devices based on the log
  // Log shows: USB string descriptor 1: "Back-UPS ES 700G FW:871.O4 .I USB FW:O4"
  ESP_LOGD(APC_HID_TAG, "Trying to read firmware from USB Product string descriptor (index 1)");
  std::string product_with_firmware;
  esp_err_t product_ret = parent_->usb_get_string_descriptor(1, product_with_firmware);
  
  if (product_ret == ESP_OK && !product_with_firmware.empty() && 
      product_with_firmware.find("FW:") != std::string::npos) {
    size_t fw_start = product_with_firmware.find("FW:");
    if (fw_start != std::string::npos) {
      // Extract firmware info from product string - look for pattern "FW:871.O4"
      std::string extracted_fw = product_with_firmware.substr(fw_start);
      size_t fw_end = extracted_fw.find(' ', 3); // Find space after "FW:xxx"
      if (fw_end != std::string::npos) {
        extracted_fw = extracted_fw.substr(0, fw_end);
      }
      data.device.firmware_version = extracted_fw;
      
      // Extract auxiliary firmware info from product string
      // Format: "FW:871.O4" → aux="O4"
      size_t fw_dot_pos = extracted_fw.find('.');
      if (fw_dot_pos != std::string::npos && fw_dot_pos < extracted_fw.length() - 1) {
        std::string after_fw_dot = extracted_fw.substr(fw_dot_pos + 1);
        // Remove "FW:" prefix if present
        if (after_fw_dot.length() >= 2) {
          data.device.firmware_aux = after_fw_dot;
          ESP_LOGI(APC_HID_TAG, "Extracted APC firmware aux from product: \"%s\"", data.device.firmware_aux.c_str());
        }
      }
      
      ESP_LOGI(APC_HID_TAG, "Successfully extracted firmware from USB Product descriptor: \"%s\"", 
               data.device.firmware_version.c_str());
      return;
    }
  } else {
    ESP_LOGD(APC_HID_TAG, "Failed to read USB Product descriptor or no FW info found: %s", 
             esp_err_to_name(product_ret));
  }
  
  // FALLBACK 1B: Parse firmware from the model string if already available
  if (!data.device.model.empty() && data.device.model.find("FW:") != std::string::npos) {
    size_t fw_start = data.device.model.find("FW:");
    if (fw_start != std::string::npos) {
      std::string model_fw = data.device.model.substr(fw_start);
      size_t fw_end = model_fw.find(' ', 3);
      if (fw_end != std::string::npos) {
        model_fw = model_fw.substr(0, fw_end);
      }
      data.device.firmware_version = model_fw;
      ESP_LOGI(APC_HID_TAG, "Firmware version extracted from model field: %s", data.device.firmware_version.c_str());
      return;
    }
  }
  
  // FALLBACK 2: Try to extract ASCII firmware string from HID report data
  std::string firmware_str;
  for (size_t i = 1; i < report.data.size() && report.data[i] != 0; i++) {
    if (report.data[i] >= 32 && report.data[i] <= 126) { // Printable ASCII
      firmware_str += static_cast<char>(report.data[i]);
    }
  }
  
  if (!firmware_str.empty() && firmware_str != "APC" && firmware_str != data.device.manufacturer) {
    data.device.firmware_version = firmware_str;
    ESP_LOGI(APC_HID_TAG, "Firmware version from HID data: %s", data.device.firmware_version.c_str());
    return;
  }
  
  // FALLBACK 3: Try to parse binary version data as last resort
  if (report.data.size() >= 3) {
    char firmware_fallback[32];
    snprintf(firmware_fallback, sizeof(firmware_fallback), "FW:%d.%d", 
             report.data[1], report.data[2]);
    data.device.firmware_version = firmware_fallback;
    ESP_LOGD(APC_HID_TAG, "Using binary firmware version fallback: %s", data.device.firmware_version.c_str());
  } else {
    // No firmware version could be determined
    data.device.firmware_version.clear();
    ESP_LOGW(APC_HID_TAG, "Unable to determine firmware version from any source");
  }
}

void ApcHidProtocol::parse_beeper_status_report(const HidReport &report, UpsData &data) {
  // Parse APC beeper status based on NUT UPS.PowerSummary.AudibleAlarmControl
  // NUT debug shows: ReportID: APC_REPORT_ID_AUDIBLE_ALARM, Value: 2 (AudibleAlarmControl)
  // APC beeper mapping: 1=disabled, 2=enabled, 3=muted
  if (report.data.size() < 2) {
    ESP_LOGV(APC_HID_TAG, "Beeper status report too short: %zu bytes", report.data.size());
    return;
  }
  
  uint8_t beeper_value = report.data[1];
  ESP_LOGD(APC_HID_TAG, "Raw APC beeper from report 0x%02X: 0x%02X (%d)", APC_REPORT_ID_AUDIBLE_ALARM, beeper_value, beeper_value);
  
  // DYNAMIC BEEPER STATUS MAPPING: Handle known APC values with intelligent fallbacks
  switch (beeper_value) {
    case 1:
      data.config.beeper_status = "disabled";
      ESP_LOGI(APC_HID_TAG, "APC beeper status: disabled (raw: %d)", beeper_value);
      break;
    case 2:
      data.config.beeper_status = "enabled";
      ESP_LOGI(APC_HID_TAG, "APC beeper status: enabled (raw: %d)", beeper_value);
      break;
    case 3:
      data.config.beeper_status = "muted";
      ESP_LOGI(APC_HID_TAG, "APC beeper status: muted (raw: %d)", beeper_value);
      break;
    case 0:
      data.config.beeper_status = "disabled";
      ESP_LOGI(APC_HID_TAG, "APC beeper status: disabled (zero value) (raw: %d)", beeper_value);
      break;
    default:
      // DYNAMIC HANDLING: For unknown values, provide better context
      if (beeper_value >= 100) {
        // Large values might indicate report format issue
        ESP_LOGW(APC_HID_TAG, "Unexpected large APC beeper value: %d (0x%02X) - possible report format issue", 
                 beeper_value, beeper_value);
        
        // Try alternative parsing - some APC models might use different byte
        if (report.data.size() >= 3) {
          uint8_t alt_value = report.data[2];
          ESP_LOGD(APC_HID_TAG, "Trying alternative beeper parsing from byte[2]: %d", alt_value);
          
          if (alt_value <= 3) {
            switch (alt_value) {
              case 0:
              case 1: data.config.beeper_status = "disabled"; break;
              case 2: data.config.beeper_status = "enabled"; break;
              case 3: data.config.beeper_status = "muted"; break;
            }
            ESP_LOGI(APC_HID_TAG, "APC beeper status (alt parsing): %s (raw: %d)", 
                     data.config.beeper_status.c_str(), alt_value);
            return;
          }
        }
        
        // Fallback for large values - use boolean logic
        data.config.beeper_status = "enabled";  // Assume enabled for non-zero large values
        ESP_LOGW(APC_HID_TAG, "Using default 'enabled' beeper due to unexpected value: %d", beeper_value);
      } else {
        // Values 4-99 - extend mapping for future APC models
        if (beeper_value >= 4 && beeper_value <= 10) {
          // Map higher values to muted/custom modes
          data.config.beeper_status = "muted";
          ESP_LOGI(APC_HID_TAG, "APC beeper status: muted (extended value) (raw: %d)", beeper_value);
        } else {
          // General fallback - use boolean interpretation
          data.config.beeper_status = (beeper_value == 0) ? "disabled" : "enabled";
          ESP_LOGW(APC_HID_TAG, "Unknown APC beeper value %d, using boolean interpretation: %s", 
                   beeper_value, data.config.beeper_status.c_str());
        }
      }
      break;
  }
}

void ApcHidProtocol::parse_input_sensitivity_report(const HidReport &report, UpsData &data) {
  // Parse APC input sensitivity based on NUT UPS.Input.APCSensitivity
  // NUT debug shows: ReportID: APC_REPORT_ID_SENSITIVITY, Value: 1 (APCSensitivity)
  // APC sensitivity mapping: 0=high, 1=normal/medium, 2=low
  if (report.data.size() < 2) {
    ESP_LOGV(APC_HID_TAG, "Input sensitivity report too short: %zu bytes", report.data.size());
    return;
  }
  
  uint8_t sensitivity_value = report.data[1];
  ESP_LOGD(APC_HID_TAG, "Raw APC sensitivity from report 0x%02X: 0x%02X (%d)", APC_REPORT_ID_SENSITIVITY, sensitivity_value, sensitivity_value);
  
  // DYNAMIC SENSITIVITY MAPPING: Handle known APC values and provide intelligent fallbacks
  switch (sensitivity_value) {
    case 0:
      data.config.input_sensitivity = "high";
      ESP_LOGI(APC_HID_TAG, "APC Input sensitivity: high (raw: %d)", sensitivity_value);
      break;
    case 1:
      data.config.input_sensitivity = "normal";
      ESP_LOGI(APC_HID_TAG, "APC Input sensitivity: normal (raw: %d)", sensitivity_value);
      break;
    case 2:
      data.config.input_sensitivity = "low";
      ESP_LOGI(APC_HID_TAG, "APC Input sensitivity: low (raw: %d)", sensitivity_value);
      break;
    default:
      // DYNAMIC HANDLING: For unknown values, provide more context and try to infer
      if (sensitivity_value >= 100) {
        // Large values might indicate different encoding or report format issue
        ESP_LOGW(APC_HID_TAG, "Unexpected large sensitivity value: %d (0x%02X) - possible report format issue", 
                 sensitivity_value, sensitivity_value);
        
        // Try alternative parsing - some APC models might use different byte
        if (report.data.size() >= 3) {
          uint8_t alt_value = report.data[2];
          ESP_LOGD(APC_HID_TAG, "Trying alternative sensitivity parsing from byte[2]: %d", alt_value);
          
          if (alt_value <= 2) {
            sensitivity_value = alt_value;
            switch (sensitivity_value) {
              case 0: data.config.input_sensitivity = "high"; break;
              case 1: data.config.input_sensitivity = "normal"; break;
              case 2: data.config.input_sensitivity = "low"; break;
            }
            ESP_LOGI(APC_HID_TAG, "APC Input sensitivity (alt parsing): %s (raw: %d)", 
                     data.config.input_sensitivity.c_str(), sensitivity_value);
            return;
          }
        }
        
        data.config.input_sensitivity = "unknown";
        ESP_LOGW(APC_HID_TAG, "Unknown APC sensitivity value: %d - please report this for future support", 
                  sensitivity_value);
      } else {
        // Values 3-99 - extend mapping dynamically
        if (sensitivity_value == 3) {
          data.config.input_sensitivity = "auto";
          ESP_LOGI(APC_HID_TAG, "APC Input sensitivity: auto (raw: %d)", sensitivity_value);
        } else {
          data.config.input_sensitivity = "unknown";
          ESP_LOGW(APC_HID_TAG, "Unknown APC sensitivity value: %d - please report this for future support", 
                   sensitivity_value);
        }
      }
      break;
  }
}

void ApcHidProtocol::read_missing_dynamic_values(UpsData &data) {
  ESP_LOGD(APC_HID_TAG, "Reading APC missing dynamic values from NUT analysis...");
  
  // 1. Battery voltage nominal (Report APC_REPORT_ID_BATTERY_VOLTAGE_NOMINAL)
  HidReport battery_voltage_nominal_report;
  if (read_hid_report(APC_REPORT_ID_BATTERY_VOLTAGE_NOMINAL, battery_voltage_nominal_report)) {
    parse_battery_voltage_nominal_report(battery_voltage_nominal_report, data);
  }
  
  // 1b. Battery voltage actual (Report APC_REPORT_ID_BATTERY_VOLTAGE) - MISSING from original implementation
  HidReport battery_voltage_report;
  if (read_hid_report(APC_REPORT_ID_BATTERY_VOLTAGE, battery_voltage_report)) {
    parse_battery_voltage_actual_report(battery_voltage_report, data);
  }
  
  // 2. Input voltage nominal (Report APC_REPORT_ID_INPUT_VOLTAGE_NOMINAL)
  HidReport input_voltage_nominal_report;
  if (read_hid_report(APC_REPORT_ID_INPUT_VOLTAGE_NOMINAL, input_voltage_nominal_report)) {
    parse_input_voltage_nominal_report(input_voltage_nominal_report, data);
  }
  
  // 3. Input transfer limits (Reports APC_REPORT_ID_INPUT_TRANSFER_LOW, APC_REPORT_ID_INPUT_TRANSFER_HIGH)
  HidReport input_transfer_low_report;
  if (read_hid_report(APC_REPORT_ID_INPUT_TRANSFER_LOW, input_transfer_low_report)) {
    parse_input_transfer_limits_report(input_transfer_low_report, data);
  }
  
  HidReport input_transfer_high_report;
  if (read_hid_report(APC_REPORT_ID_INPUT_TRANSFER_HIGH, input_transfer_high_report)) {
    parse_input_transfer_limits_report(input_transfer_high_report, data);
  }
  
  // 4. Battery runtime low threshold (Report APC_REPORT_ID_BATTERY_RUNTIME_LOW)
  HidReport battery_runtime_low_report;
  if (read_hid_report(APC_REPORT_ID_BATTERY_RUNTIME_LOW, battery_runtime_low_report)) {
    parse_battery_runtime_low_report(battery_runtime_low_report, data);
  }
  
  // 5. Manufacturing dates (Reports APC_REPORT_ID_MFR_DATE_UPS, APC_REPORT_ID_MFR_DATE_BATTERY, 0x7b)
  HidReport power_summary_mfr_date_report;
  if (read_hid_report(APC_REPORT_ID_MFR_DATE_UPS, power_summary_mfr_date_report)) {
    parse_manufacture_date_report(power_summary_mfr_date_report, data, false); // UPS mfr date
  }
  
  HidReport battery_mfr_date_report;
  if (read_hid_report(APC_REPORT_ID_MFR_DATE_BATTERY, battery_mfr_date_report)) {
    parse_manufacture_date_report(battery_mfr_date_report, data, true); // Battery mfr date
  }
  
  // 6. UPS delay shutdown (Report APC_REPORT_ID_DELAY_SHUTDOWN)
  HidReport ups_delay_shutdown_report;
  if (read_hid_report(APC_REPORT_ID_DELAY_SHUTDOWN, ups_delay_shutdown_report)) {
    parse_ups_delay_shutdown_report(ups_delay_shutdown_report, data);
  }

  // 7. UPS delay reboot (Report APC_REPORT_ID_DELAY_REBOOT)  
  HidReport ups_delay_reboot_report;
  if (read_hid_report(APC_REPORT_ID_DELAY_REBOOT, ups_delay_reboot_report)) {
    parse_ups_delay_reboot_report(ups_delay_reboot_report, data);
  }
  
  // 7. Battery charge thresholds (Reports APC_REPORT_ID_CHARGE_WARNING, APC_REPORT_ID_CHARGE_LOW)
  HidReport battery_charge_warning_report;
  if (read_hid_report(APC_REPORT_ID_CHARGE_WARNING, battery_charge_warning_report)) {
    parse_battery_charge_threshold_report(battery_charge_warning_report, data, false); // warning
  }
  
  HidReport battery_charge_low_report;
  if (read_hid_report(APC_REPORT_ID_CHARGE_LOW, battery_charge_low_report)) {
    parse_battery_charge_threshold_report(battery_charge_low_report, data, true); // low
  }
  
  // 8. Battery chemistry/type (shared report ID)
  HidReport battery_chemistry_report;
  if (read_hid_report(battery_chemistry::REPORT_ID, battery_chemistry_report)) {
    parse_battery_chemistry_report(battery_chemistry_report, data);
  }
  
  // Set timer values based on delay settings (negative indicates no active countdown)
  // NUT shows these as derived from delay values when no countdown is active
  data.test.timer_shutdown = -static_cast<int16_t>(data.config.delay_shutdown);
  data.test.timer_start = -static_cast<int16_t>(data.config.delay_start);
  // timer_reboot is set in parse_ups_delay_reboot_report() if available
  
  // ups.firmware.aux needs to be extracted from firmware string
  // This will be handled in the existing firmware parsing logic
  
  // Set battery status based on current battery level and charging state
  if (!std::isnan(data.battery.level)) {
    if (data.battery.level >= 90) {
      data.battery.status = battery_status::FULL;
    } else if (data.battery.level >= 20) {
      data.battery.status = battery_status::GOOD;
    } else if (data.battery.level >= 10) {
      data.battery.status = battery_status::LOW;
    } else {
      data.battery.status = battery_status::CRITICAL;
    }
    ESP_LOGI(APC_HID_TAG, "APC Battery status: %s (%.0f%%)", data.battery.status.c_str(), data.battery.level);
  }
  
  // 8. Test result reading (Report APC_REPORT_ID_TEST_RESULT - same as test command)
  // Based on NUT: "UPS.Battery.Test" maps to test result
  HidReport test_result_report;
  if (read_hid_report(APC_REPORT_ID_TEST_RESULT, test_result_report)) {
    parse_test_result_report(test_result_report, data);
  }
  
  ESP_LOGD(APC_HID_TAG, "Completed reading APC missing dynamic values");
}

void ApcHidProtocol::parse_battery_voltage_nominal_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Battery voltage nominal report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_BATTERY_VOLTAGE_NOMINAL, Value: 12 (UPS.Battery.ConfigVoltage)
  // Data format: [ID, volt_low, volt_high] - 16-bit little endian
  // CRITICAL FIX: Raw value 1200 needs to be scaled to 12.0V (divide by 100)
  uint16_t voltage_raw = report.data[1] | (report.data[2] << 8);
  data.battery.voltage_nominal = static_cast<float>(voltage_raw) / battery::MAX_LEVEL_PERCENT;
  
  ESP_LOGI(APC_HID_TAG, "APC Battery voltage nominal: %.1fV (raw: 0x%02X%02X = %d, scaled from %d)", 
           data.battery.voltage_nominal, report.data[2], report.data[1], voltage_raw, voltage_raw);
}

void ApcHidProtocol::parse_battery_voltage_actual_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Battery voltage actual report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_BATTERY_VOLTAGE, Value: 13.67 (UPS.Battery.Voltage)
  // Data format: [ID, volt_low, volt_high] - 16-bit little endian
  // The value should be similar to 13.67V based on NUT debug
  uint16_t voltage_raw = report.data[1] | (report.data[2] << 8);
  
  // Try different scaling factors to match NUT value of ~13.67V
  float voltage_candidate1 = static_cast<float>(voltage_raw) / battery::MAX_LEVEL_PERCENT;  // Same as nominal
  float voltage_candidate2 = static_cast<float>(voltage_raw) / battery::VOLTAGE_SCALE_FACTOR;   // Less scaling
  float voltage_candidate3 = static_cast<float>(voltage_raw);           // No scaling
  
  // Choose the one closest to expected battery voltage range (10-15V)
  if (voltage_candidate1 >= battery::VOLTAGE_SCALE_FACTOR && voltage_candidate1 <= 20.0f) {
    data.battery.voltage = voltage_candidate1;
    ESP_LOGI(APC_HID_TAG, "APC Battery voltage: %.2fV (raw: 0x%02X%02X = %d, scaled /100)", 
             data.battery.voltage, report.data[2], report.data[1], voltage_raw);
  } else if (voltage_candidate2 >= battery::VOLTAGE_SCALE_FACTOR && voltage_candidate2 <= 20.0f) {
    data.battery.voltage = voltage_candidate2;
    ESP_LOGI(APC_HID_TAG, "APC Battery voltage: %.2fV (raw: 0x%02X%02X = %d, scaled /10)", 
             data.battery.voltage, report.data[2], report.data[1], voltage_raw);
  } else if (voltage_candidate3 >= battery::VOLTAGE_SCALE_FACTOR && voltage_candidate3 <= 20.0f) {
    data.battery.voltage = voltage_candidate3;
    ESP_LOGI(APC_HID_TAG, "APC Battery voltage: %.2fV (raw: 0x%02X%02X = %d, no scaling)", 
             data.battery.voltage, report.data[2], report.data[1], voltage_raw);
  } else {
    ESP_LOGW(APC_HID_TAG, "APC Battery voltage out of expected range: raw=%d, candidates: %.2f, %.2f, %.2f", 
             voltage_raw, voltage_candidate1, voltage_candidate2, voltage_candidate3);
    data.battery.voltage = voltage_candidate1; // Default to /100 scaling
  }
}

void ApcHidProtocol::parse_input_voltage_nominal_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Input voltage nominal report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_INPUT_VOLTAGE_NOMINAL, Value: 230 (UPS.Input.ConfigVoltage)
  // Data format: [ID, volt_low, volt_high] - 16-bit little endian
  uint16_t voltage_raw = report.data[1] | (report.data[2] << 8);
  data.power.input_voltage_nominal = static_cast<float>(voltage_raw);
  
  ESP_LOGI(APC_HID_TAG, "APC Input voltage nominal: %.0fV (raw: 0x%02X%02X = %d)", 
           data.power.input_voltage_nominal, report.data[2], report.data[1], voltage_raw);
}

void ApcHidProtocol::parse_input_transfer_limits_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Input transfer limits report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Data format: [ID, limit_low, limit_high] - 16-bit little endian
  uint16_t limit_raw = report.data[1] | (report.data[2] << 8);
  
  if (report.report_id == APC_REPORT_ID_INPUT_TRANSFER_LOW) {
    // NUT debug: ReportID: APC_REPORT_ID_INPUT_TRANSFER_LOW, Value: 180 (UPS.Input.LowVoltageTransfer)
    data.power.input_transfer_low = static_cast<float>(limit_raw);
    ESP_LOGI(APC_HID_TAG, "APC Input transfer low: %.0fV (raw: 0x%02X%02X = %d)", 
             data.power.input_transfer_low, report.data[2], report.data[1], limit_raw);
  } else if (report.report_id == APC_REPORT_ID_INPUT_TRANSFER_HIGH) {
    // NUT debug: ReportID: APC_REPORT_ID_INPUT_TRANSFER_HIGH, Value: 266 (UPS.Input.HighVoltageTransfer)
    data.power.input_transfer_high = static_cast<float>(limit_raw);
    ESP_LOGI(APC_HID_TAG, "APC Input transfer high: %.0fV (raw: 0x%02X%02X = %d)", 
             data.power.input_transfer_high, report.data[2], report.data[1], limit_raw);
  }
}

void ApcHidProtocol::parse_battery_runtime_low_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Battery runtime low report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_BATTERY_RUNTIME_LOW, Value: 120 (UPS.Battery.RemainingTimeLimit)
  // Data format: [ID, time_low, time_high] - 16-bit little endian
  uint16_t time_raw = report.data[1] | (report.data[2] << 8);
  data.battery.runtime_low = static_cast<float>(time_raw);
  
  ESP_LOGI(APC_HID_TAG, "APC Battery runtime low threshold: %.0f minutes (raw: 0x%02X%02X = %d)", 
           data.battery.runtime_low, report.data[2], report.data[1], time_raw);
}

void ApcHidProtocol::parse_manufacture_date_report(const HidReport &report, UpsData &data, bool is_battery) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "Manufacture date report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug shows: Value: 19257 for date "2017/09/25"
  // Data format: [ID, date_low, date_high] - 16-bit little endian
  // CRITICAL FIX: Raw value 0x4B39=19257 but actual device shows different value
  // Let's see what value we actually get from this device
  uint16_t date_raw = report.data[1] | (report.data[2] << 8);
  ESP_LOGW(APC_HID_TAG, "DEBUG: Date raw bytes: 0x%02X 0x%02X = %d", report.data[1], report.data[2], date_raw);
  std::string date_str = convert_apc_date(date_raw);
  
  if (is_battery) {
    data.battery.mfr_date = date_str;
    ESP_LOGI(APC_HID_TAG, "APC Battery manufacture date: %s (raw: %d)", 
             data.battery.mfr_date.c_str(), date_raw);
  } else {
    data.device.mfr_date = date_str;
    ESP_LOGI(APC_HID_TAG, "APC UPS manufacture date: %s (raw: %d)", 
             data.device.mfr_date.c_str(), date_raw);
  }
}

void ApcHidProtocol::parse_ups_delay_shutdown_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 3) {
    ESP_LOGW(APC_HID_TAG, "UPS delay shutdown report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_DELAY_SHUTDOWN, Value: -1 (but NUT output shows ups.delay.shutdown: 20)
  // This suggests NUT does additional processing/conversion
  // Data format: [ID, delay_low, delay_high] - 16-bit signed little endian
  int16_t delay_raw = static_cast<int16_t>(report.data[1] | (report.data[2] << 8));
  
  if (delay_raw == -1) {
    // NUT shows 20 seconds for this APC model when HID shows -1
    // This is likely a model-specific default value
    data.config.delay_shutdown = 20;  // Use NUT's processed value
    ESP_LOGI(APC_HID_TAG, "APC UPS delay shutdown: %d seconds (processed from HID value %d)", 
             data.config.delay_shutdown, delay_raw);
  } else {
    data.config.delay_shutdown = delay_raw;
    ESP_LOGI(APC_HID_TAG, "APC UPS delay shutdown: %d seconds (raw: %d)", 
             data.config.delay_shutdown, delay_raw);
  }
}

void ApcHidProtocol::parse_ups_delay_reboot_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "UPS delay reboot report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_DELAY_REBOOT, Value: 0 
  // APC uses 8-bit value for reboot delay
  uint8_t delay_raw = report.data[1];
  
  // Set both delay and timer values
  data.config.delay_reboot = static_cast<int16_t>(delay_raw);
  data.test.timer_reboot = -static_cast<int16_t>(delay_raw);  // Negative indicates no active countdown
  
  ESP_LOGI(APC_HID_TAG, "APC UPS delay reboot: %d seconds", data.config.delay_reboot);
}

std::string ApcHidProtocol::convert_apc_date(uint16_t date_value) {
  ESP_LOGD(APC_HID_TAG, "Converting USB PDC date value: %u (0x%04X)", date_value, date_value);
  
  if (date_value == 0) {
    return "not set";
  }
  
  // USB Power Device Class date format (per USB PDC spec v1.1, page 38):
  // ManufacturerDate: The date the pack was manufactured in a packed integer.
  // The date is packed as: (year – 1980)*512 + month*32 + day
  // This matches NUT's date_conversion_fun() in usbhid-ups.c
  
  // Extract date components using bit operations (matching NUT implementation)
  int day = date_value & 0x1F;           // Last 5 bits (0-31)
  int month = (date_value >> 5) & 0x0F;  // Next 4 bits (0-15, but valid 1-12)  
  int year = 1980 + (date_value >> 9);   // Upper bits shifted right 9 positions + 1980
  
  ESP_LOGD(APC_HID_TAG, "USB PDC date extraction: day=%d, month=%d, year=%d", day, month, year);
  
  // Validate date components
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    ESP_LOGW(APC_HID_TAG, "Invalid date components: year=%d, month=%d, day=%d", year, month, day);
    return "invalid date";
  }
  
  char date_str[16];
  snprintf(date_str, sizeof(date_str), "%04d/%02d/%02d", year, month, day);
  
  ESP_LOGD(APC_HID_TAG, "Converted USB PDC date %u to %s", date_value, date_str);
  return std::string(date_str);
}

void ApcHidProtocol::parse_battery_charge_threshold_report(const HidReport &report, UpsData &data, bool is_low_threshold) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Battery charge threshold report too short: %zu bytes", report.data.size());
    return;
  }
  
  // Data format: [ID, threshold] - single byte percentage
  uint8_t threshold_raw = report.data[1];
  
  if (is_low_threshold) {
    // NUT debug: ReportID: APC_REPORT_ID_CHARGE_LOW, Value: 10 (RemainingCapacityLimit)
    data.battery.charge_low = static_cast<float>(threshold_raw);
    ESP_LOGI(APC_HID_TAG, "APC Battery charge low threshold: %.0f%% (raw: %d)", 
             data.battery.charge_low, threshold_raw);
  } else {
    // NUT debug: ReportID: APC_REPORT_ID_CHARGE_WARNING, Value: 50 (WarningCapacityLimit)
    data.battery.charge_warning = static_cast<float>(threshold_raw);
    ESP_LOGI(APC_HID_TAG, "APC Battery charge warning threshold: %.0f%% (raw: %d)", 
             data.battery.charge_warning, threshold_raw);
  }
}

void ApcHidProtocol::parse_battery_chemistry_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Battery chemistry report too short: %zu bytes", report.data.size());
    return;
  }
  
  // NUT debug: ReportID: APC_REPORT_ID_BATTERY_CHEMISTRY, Value: 4 (iDeviceChemistry)
  uint8_t chemistry_raw = report.data[1];
  
  // Map chemistry values based on NUT libhid implementation
  data.battery.type = battery_chemistry::id_to_string(chemistry_raw);
  
  if (data.battery.type == battery_chemistry::UNKNOWN) {
    ESP_LOGW(APC_HID_TAG, "Unknown APC battery chemistry value: %d", chemistry_raw);
  }
  
  ESP_LOGI(APC_HID_TAG, "APC Battery chemistry: %s (raw: %d)", 
           data.battery.type.c_str(), chemistry_raw);
}

bool ApcHidProtocol::beeper_enable() {
  ESP_LOGD(APC_HID_TAG, "Sending APC beeper enable command");
  
  // APC DEVICE SPECIFIC: From NUT debug, your device supports TWO beeper report IDs:
  // APC_REPORT_ID_AUDIBLE_ALARM: UPS.PowerSummary.AudibleAlarmControl
  // APC_REPORT_ID_AUDIBLE_BEEPER: UPS.AudibleAlarmControl  
  uint8_t report_ids_to_try[] = {APC_REPORT_ID_AUDIBLE_ALARM, APC_REPORT_ID_AUDIBLE_BEEPER, APC_REPORT_ID_BEEPER, APC_REPORT_ID_POWER_SUMMARY};
  
  for (size_t i = 0; i < sizeof(report_ids_to_try); i++) {
    uint8_t report_id = report_ids_to_try[i];
    ESP_LOGD(APC_HID_TAG, "Trying beeper enable with report ID 0x%02X", report_id);
    
    uint8_t beeper_data[2] = {report_id, beeper::CONTROL_ENABLE};  // Report ID, Value=2 (enabled)
    
#ifdef USE_ESP32
    esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, report_id, beeper_data, sizeof(beeper_data), parent_->get_protocol_timeout());
    if (ret == ESP_OK) {
      ESP_LOGI(APC_HID_TAG, "APC beeper enabled successfully with report ID 0x%02X", report_id);
      return true;
    } else {
      ESP_LOGD(APC_HID_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
#else
    // Simulation mode - always succeed
    if (parent_->get_simulation_mode()) {
      ESP_LOGI(APC_HID_TAG, "Simulated: APC beeper enabled successfully with report ID 0x%02X", report_id);
      return true;
    }
    ESP_LOGW(APC_HID_TAG, "HID communication not available on this platform");
    return false;
#endif
  }
  
  ESP_LOGW(APC_HID_TAG, "Failed to enable APC beeper with all tested report IDs");
  return false;
}

bool ApcHidProtocol::beeper_disable() {
  ESP_LOGD(APC_HID_TAG, "Sending APC beeper disable command");
  
  // APC DEVICE SPECIFIC: From NUT debug, your device supports TWO beeper report IDs:
  // APC_REPORT_ID_AUDIBLE_ALARM: UPS.PowerSummary.AudibleAlarmControl
  // APC_REPORT_ID_AUDIBLE_BEEPER: UPS.AudibleAlarmControl  
  uint8_t report_ids_to_try[] = {APC_REPORT_ID_AUDIBLE_ALARM, APC_REPORT_ID_AUDIBLE_BEEPER, APC_REPORT_ID_BEEPER, APC_REPORT_ID_POWER_SUMMARY};
  
  for (size_t i = 0; i < sizeof(report_ids_to_try); i++) {
    uint8_t report_id = report_ids_to_try[i];
    ESP_LOGD(APC_HID_TAG, "Trying beeper disable with report ID 0x%02X", report_id);
    
    uint8_t beeper_data[2] = {report_id, beeper::CONTROL_DISABLE};  // Report ID, Value=1 (disabled)
    
    esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, report_id, beeper_data, sizeof(beeper_data), parent_->get_protocol_timeout());
    if (ret == ESP_OK) {
      ESP_LOGI(APC_HID_TAG, "APC beeper disabled successfully with report ID 0x%02X", report_id);
      return true;
    } else {
      ESP_LOGD(APC_HID_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }
  
  ESP_LOGW(APC_HID_TAG, "Failed to disable APC beeper with all tested report IDs");
  return false;
}

bool ApcHidProtocol::beeper_mute() {
  ESP_LOGD(APC_HID_TAG, "Sending APC beeper mute command");
  
  // MUTE FUNCTIONALITY (Value 3):
  // - Acknowledges and silences current active alarms
  // - Beeper may still sound for new critical events  
  // - Different from DISABLE (1) which turns off beeper completely
  // - Current device status shows "enabled" (2), mute changes to "muted" (3)
  
  uint8_t report_ids_to_try[] = {APC_REPORT_ID_AUDIBLE_ALARM, APC_REPORT_ID_AUDIBLE_BEEPER};
  
  for (size_t i = 0; i < sizeof(report_ids_to_try); i++) {
    uint8_t report_id = report_ids_to_try[i];
    ESP_LOGD(APC_HID_TAG, "Trying beeper mute (acknowledge alarms) with report ID 0x%02X", report_id);
    
    uint8_t beeper_data[2] = {report_id, beeper::CONTROL_MUTE};  // Report ID, Value=3 (muted/acknowledged)
    
    esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, report_id, beeper_data, sizeof(beeper_data), parent_->get_protocol_timeout());
    if (ret == ESP_OK) {
      ESP_LOGI(APC_HID_TAG, "APC beeper muted (current alarms acknowledged) with report ID 0x%02X", report_id);
      return true;
    } else {
      ESP_LOGD(APC_HID_TAG, "Failed with report ID 0x%02X: %s", report_id, esp_err_to_name(ret));
    }
  }
  
  ESP_LOGW(APC_HID_TAG, "Failed to mute APC beeper with all tested report IDs");
  return false;
}

bool ApcHidProtocol::beeper_test() {
  ESP_LOGD(APC_HID_TAG, "Starting APC beeper test sequence");
  
  // First, read current beeper status to restore later
  HidReport current_report;
  if (!read_hid_report(APC_REPORT_ID_AUDIBLE_ALARM, current_report)) {
    ESP_LOGW(APC_HID_TAG, "Failed to read current beeper status for test");
    return false;
  }
  
  uint8_t original_state = (current_report.data.size() >= 2) ? current_report.data[1] : beeper::CONTROL_ENABLE;
  ESP_LOGI(APC_HID_TAG, "Original beeper state: %d", original_state);
  
  // For APC beeper test, we need to:
  // 1. Enable beeper first (if disabled)
  // 2. Wait for beeper to sound (longer delay)
  // 3. Disable beeper to stop the test sound
  // 4. Restore original state
  
  // FOCUS ON ENABLE/DISABLE: Since NUT shows beeper currently "enabled" (value=2)
  // Test by disabling first (may be audible), then re-enabling
  ESP_LOGI(APC_HID_TAG, "Step 1: Disabling beeper (from current enabled state)");
  if (!beeper_disable()) {
    ESP_LOGW(APC_HID_TAG, "Failed to disable beeper for test");
    return false;
  }
  
  ESP_LOGI(APC_HID_TAG, "Step 2: Waiting 3 seconds with beeper disabled");
  vTaskDelay(pdMS_TO_TICKS(3000));
  
  ESP_LOGI(APC_HID_TAG, "Step 3: Re-enabling beeper");
  if (!beeper_enable()) {
    ESP_LOGW(APC_HID_TAG, "Failed to re-enable beeper");
    // Don't return false - continue to restore original state
  }
  
  // Brief delay before restoration
  vTaskDelay(pdMS_TO_TICKS(500));
  
  // Step 4: Restore original beeper state
  ESP_LOGI(APC_HID_TAG, "Step 4: Restoring original beeper state: %d", original_state);
  uint8_t restore_data[2] = {APC_REPORT_ID_AUDIBLE_ALARM, original_state};
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_AUDIBLE_ALARM, restore_data, sizeof(restore_data), parent_->get_protocol_timeout());
  
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "APC beeper test sequence completed successfully");
    return true;
  } else {
    ESP_LOGW(APC_HID_TAG, "Beeper test completed but failed to restore original state: %s", esp_err_to_name(ret));
    return true; // Test succeeded even if restore failed
  }
}

// UPS and Battery Test implementations based on NUT analysis
bool ApcHidProtocol::start_battery_test_quick() {
  ESP_LOGI(APC_HID_TAG, "Starting APC quick battery test");
  
  // Check if device supports SET_REPORT operations
  if (!parent_->get_vendor_id()) {
    ESP_LOGW(APC_HID_TAG, "Device not available for test commands");
    return false;
  }
  
  // APC Back-UPS ES 700G (PID=usb::PRODUCT_ID_APC_BACK_UPS_ES_700) is INPUT-ONLY and doesn't support HID SET_REPORT
  uint16_t product_id = parent_->get_product_id();
  if (product_id == usb::PRODUCT_ID_APC_BACK_UPS_ES_700) {
    ESP_LOGW(APC_HID_TAG, "APC Back-UPS ES 700G (PID=0x%04X) is INPUT-ONLY device - battery tests not supported via HID", usb::PRODUCT_ID_APC_BACK_UPS_ES_700);
    ESP_LOGI(APC_HID_TAG, "Tip: Use the physical TEST button on the UPS instead");
    return false;
  }
  
  // For supported models: Based on NUT debug logs, APC uses report ID APC_REPORT_ID_TEST_RESULT for battery test
  // Command value 1 = Quick test (based on NUT test_write_info struct)
  uint8_t test_data[2] = {APC_REPORT_ID_TEST_RESULT, test::COMMAND_QUICK};
  
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_TEST_RESULT, test_data, sizeof(test_data), parent_->get_protocol_timeout());
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "APC quick battery test command sent successfully");
    return true;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to send APC quick battery test: %s", esp_err_to_name(ret));
    ESP_LOGI(APC_HID_TAG, "This may be an INPUT-ONLY device - use physical TEST button on UPS");
    return false;
  }
}

bool ApcHidProtocol::start_battery_test_deep() {
  ESP_LOGI(APC_HID_TAG, "Starting APC deep battery test");
  
  // APC Back-UPS ES 700G (PID=usb::PRODUCT_ID_APC_BACK_UPS_ES_700) is INPUT-ONLY and doesn't support HID SET_REPORT
  uint16_t product_id = parent_->get_product_id();
  if (product_id == usb::PRODUCT_ID_APC_BACK_UPS_ES_700) {
    ESP_LOGW(APC_HID_TAG, "APC Back-UPS ES 700G (PID=0x%04X) is INPUT-ONLY device - battery tests not supported via HID", usb::PRODUCT_ID_APC_BACK_UPS_ES_700);
    ESP_LOGI(APC_HID_TAG, "Tip: Use the physical TEST button on the UPS instead");
    return false;
  }
  
  // For supported models: Based on NUT debug logs, APC uses report ID APC_REPORT_ID_TEST_RESULT for battery test
  // Command value 2 = Deep test (based on NUT test_write_info struct)
  uint8_t test_data[2] = {APC_REPORT_ID_TEST_RESULT, test::COMMAND_DEEP};
  
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_TEST_RESULT, test_data, sizeof(test_data), parent_->get_protocol_timeout());
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "APC deep battery test command sent successfully");
    return true;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to send APC deep battery test: %s", esp_err_to_name(ret));
    ESP_LOGI(APC_HID_TAG, "This may be an INPUT-ONLY device - use physical TEST button on UPS");
    return false;
  }
}

bool ApcHidProtocol::stop_battery_test() {
  ESP_LOGI(APC_HID_TAG, "Stopping APC battery test");
  
  // APC Back-UPS ES 700G (PID=usb::PRODUCT_ID_APC_BACK_UPS_ES_700) is INPUT-ONLY and doesn't support HID SET_REPORT
  uint16_t product_id = parent_->get_product_id();
  if (product_id == usb::PRODUCT_ID_APC_BACK_UPS_ES_700) {
    ESP_LOGW(APC_HID_TAG, "APC Back-UPS ES 700G (PID=0x%04X) is INPUT-ONLY device - battery tests not supported via HID", usb::PRODUCT_ID_APC_BACK_UPS_ES_700);
    ESP_LOGI(APC_HID_TAG, "Physical test will stop automatically after completion");
    return false;
  }
  
  // For supported models: Based on NUT debug logs, APC uses report ID APC_REPORT_ID_TEST_RESULT for battery test
  // Command value 3 = Abort test (based on NUT test_write_info struct)
  uint8_t test_data[2] = {APC_REPORT_ID_TEST_RESULT, test::COMMAND_ABORT};
  
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_TEST_RESULT, test_data, sizeof(test_data), parent_->get_protocol_timeout());
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "APC battery test stop command sent successfully");
    return true;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to send APC battery test stop: %s", esp_err_to_name(ret));
    ESP_LOGI(APC_HID_TAG, "This may be an INPUT-ONLY device - test will stop automatically");
    return false;
  }
}

bool ApcHidProtocol::start_ups_test() {
  ESP_LOGI(APC_HID_TAG, "Starting APC UPS panel test");
  
  // Based on NUT debug logs, APC uses report ID APC_REPORT_ID_PANEL_TEST for panel test
  // Command value 1 = Start panel test (based on NUT analysis)
  uint8_t test_data[2] = {APC_REPORT_ID_PANEL_TEST, 1};
  
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_PANEL_TEST, test_data, sizeof(test_data), parent_->get_protocol_timeout());
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "APC UPS panel test command sent successfully");
    return true;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to send APC UPS panel test: %s", esp_err_to_name(ret));
    return false;
  }
}

bool ApcHidProtocol::stop_ups_test() {
  ESP_LOGI(APC_HID_TAG, "Stopping APC UPS panel test");
  
  // Based on NUT debug logs, APC uses report ID APC_REPORT_ID_PANEL_TEST for panel test
  // Command value 0 = Stop/abort panel test (based on NUT analysis)
  uint8_t test_data[2] = {APC_REPORT_ID_PANEL_TEST, 0};
  
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_PANEL_TEST, test_data, sizeof(test_data), parent_->get_protocol_timeout());
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "APC UPS panel test stop command sent successfully");
    return true;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to send APC UPS panel test stop: %s", esp_err_to_name(ret));
    return false;
  }
}

void ApcHidProtocol::parse_test_result_report(const HidReport &report, UpsData &data) {
  if (report.data.size() < 2) {
    ESP_LOGW(APC_HID_TAG, "Test result report too short: %zu bytes", report.data.size());
    data.test.ups_test_result = test::RESULT_ERROR_READING;
    return;
  }
  
  // Based on NUT test_read_info lookup table:
  // 1 = "Done and passed", 2 = "Done and warning", 3 = "Done and error",
  // 4 = "Aborted", 5 = "In progress", 6 = "No test initiated", 7 = "Test scheduled"
  uint8_t test_result_value = report.data[1];
  
  ESP_LOGD(APC_HID_TAG, "Raw test result from report 0x%02X: 0x%02X (%d)", APC_REPORT_ID_TEST_RESULT, test_result_value, test_result_value);
  
  switch (test_result_value) {
    case 1:
      data.test.ups_test_result = test::RESULT_DONE_PASSED;
      break;
    case 2:
      data.test.ups_test_result = test::RESULT_DONE_WARNING;
      break;
    case 3:
      data.test.ups_test_result = test::RESULT_DONE_ERROR;
      break;
    case 4:
      data.test.ups_test_result = test::RESULT_ABORTED;
      break;
    case 5:
      data.test.ups_test_result = test::RESULT_IN_PROGRESS;
      break;
    case 6:
      data.test.ups_test_result = test::RESULT_NO_TEST;
      break;
    case 7:
      data.test.ups_test_result = test::RESULT_SCHEDULED;
      break;
    default:
      data.test.ups_test_result = "Unknown test result (" + std::to_string(test_result_value) + ")";
      ESP_LOGW(APC_HID_TAG, "Unknown APC test result value: %d", test_result_value);
      break;
  }
  
  ESP_LOGI(APC_HID_TAG, "APC Test result: %s (raw: %d)", data.test.ups_test_result.c_str(), test_result_value);
}

void ApcHidProtocol::read_frequency_data(UpsData &data) {
  // Initialize frequency to NaN
  data.power.frequency = NAN;
  
  // Try to read frequency from various HID report IDs
  // Based on NUT reference, frequency is typically in input/output measurement reports
  
  // Report IDs commonly used for frequency measurements:
  const std::vector<uint8_t> frequency_report_ids = {
    APC_REPORT_ID_FREQUENCY,     // APC-specific config report (apparent power and frequency) - PRIORITY
    HID_USAGE_POW_FREQUENCY,     // Standard HID frequency usage
    HID_USAGE_POW_VOLTAGE,       // Input measurements (may include frequency)  
    HID_USAGE_POW_CURRENT,       // Output measurements (may include frequency)
    HID_USAGE_POW_OUTPUT,        // Output collection (might contain frequency)
    HID_USAGE_POW_INPUT,         // Input collection (might contain frequency)
  };
  
  for (uint8_t report_id : frequency_report_ids) {
    HidReport freq_report;
    if (read_hid_report(report_id, freq_report)) {
      float frequency_value = parse_frequency_from_report(freq_report);
      if (!std::isnan(frequency_value)) {
        data.power.frequency = frequency_value;
        ESP_LOGD(APC_HID_TAG, "Found frequency %.1f Hz in report 0x%02X", frequency_value, report_id);
        return;
      }
    }
  }
  
  ESP_LOGV(APC_HID_TAG, "Frequency data not available from any HID report");
}

float ApcHidProtocol::parse_frequency_from_report(const HidReport &report) {
  if (report.data.size() < 2) {
    ESP_LOGV(APC_HID_TAG, "Frequency report 0x%02X too short: %zu bytes", report.data[0], report.data.size());
    return NAN;
  }
  
  ESP_LOGD(APC_HID_TAG, "Parsing frequency from report 0x%02X (%zu bytes): %02X %02X %02X %02X", 
           report.data[0], report.data.size(), 
           report.data.size() > 0 ? report.data[0] : 0,
           report.data.size() > 1 ? report.data[1] : 0,
           report.data.size() > 2 ? report.data[2] : 0,
           report.data.size() > 3 ? report.data[3] : 0);
  
  // APC-specific method: Report APC_REPORT_ID_FREQUENCY frequency at byte[3] (based on ESP32 NUT server documentation)
  if (report.data[0] == APC_REPORT_ID_FREQUENCY) {
    ESP_LOGD(APC_HID_TAG, "APC Method - Report 0x%02X analysis: size=%zu bytes", APC_REPORT_ID_FREQUENCY, report.data.size());
    if (report.data.size() >= 4) {
      uint8_t freq_byte = report.data[3];
      ESP_LOGV(APC_HID_TAG, "APC Method - Report 0x%02X byte[3]: %d (0x%02X) - Range check: %s", APC_REPORT_ID_FREQUENCY, 
               freq_byte, freq_byte,
               (freq_byte >= FREQUENCY_MIN_VALID && freq_byte <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
      if (freq_byte >= FREQUENCY_MIN_VALID && freq_byte <= FREQUENCY_MAX_VALID) {
        ESP_LOGI(APC_HID_TAG, "Found frequency %.0f Hz using APC Method (report 0x%02X, byte[3])", static_cast<float>(freq_byte), APC_REPORT_ID_FREQUENCY);
        return static_cast<float>(freq_byte);
      }
    } else {
      ESP_LOGW(APC_HID_TAG, "APC Method - Report 0x%02X too short for frequency: only %zu bytes (need 4+)", APC_REPORT_ID_FREQUENCY, report.data.size());
      // Try alternative: byte[1] might contain frequency or frequency-derived value in some APC models
      if (report.data.size() >= 2) {
        uint8_t alt_freq = report.data[1];
        ESP_LOGV(APC_HID_TAG, "APC Method - Report 0x%02X byte[1]: %d (0x%02X)", APC_REPORT_ID_FREQUENCY, alt_freq, alt_freq);
        
        // Check if this could be a frequency indicator (100 -> 50Hz, 120 -> 60Hz)
        if (alt_freq == 100) {
          ESP_LOGI(APC_HID_TAG, "Found frequency 50 Hz using APC Method (report 0x%02X, byte[1] = 100 -> 50Hz)", APC_REPORT_ID_FREQUENCY);
          return 50.0f;
        } else if (alt_freq == 120) {
          ESP_LOGI(APC_HID_TAG, "Found frequency 60 Hz using APC Method (report 0x%02X, byte[1] = 120 -> 60Hz)", APC_REPORT_ID_FREQUENCY);
          return 60.0f;
        }
      }
    }
  }
  
  // Try different byte positions and formats commonly used for frequency
  // Most UPS devices report frequency as integer Hz (50 or 60)
  
  // Method 1: Single byte at position 1 (common for simple frequency reports)
  if (report.data.size() >= 2) {
    uint8_t freq_byte = report.data[1];
    ESP_LOGV(APC_HID_TAG, "Method 1 - Testing byte[1]: %d (0x%02X) - Range check: %s", 
             freq_byte, freq_byte,
             (freq_byte >= FREQUENCY_MIN_VALID && freq_byte <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
    if (freq_byte >= FREQUENCY_MIN_VALID && freq_byte <= FREQUENCY_MAX_VALID) {
      ESP_LOGI(APC_HID_TAG, "Found frequency %.0f Hz using Method 1 (single byte)", static_cast<float>(freq_byte));
      return static_cast<float>(freq_byte);
    }
  }
  
  // Method 2: 16-bit little-endian value at position 1-2
  if (report.data.size() >= 3) {
    uint16_t freq_word = report.data[1] | (report.data[2] << 8);
    ESP_LOGV(APC_HID_TAG, "Method 2 - Testing little-endian word[1-2]: %d (0x%04X) - Range check: %s", 
             freq_word, freq_word,
             (freq_word >= FREQUENCY_MIN_VALID && freq_word <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
    if (freq_word >= FREQUENCY_MIN_VALID && freq_word <= FREQUENCY_MAX_VALID) {
      ESP_LOGI(APC_HID_TAG, "Found frequency %.0f Hz using Method 2 (16-bit little-endian)", static_cast<float>(freq_word));
      return static_cast<float>(freq_word);
    }
  }
  
  // Method 3: 16-bit big-endian value at position 1-2
  if (report.data.size() >= 3) {
    uint16_t freq_word = (report.data[1] << 8) | report.data[2];
    ESP_LOGV(APC_HID_TAG, "Method 3 - Testing big-endian word[1-2]: %d (0x%04X) - Range check: %s", 
             freq_word, freq_word,
             (freq_word >= FREQUENCY_MIN_VALID && freq_word <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
    if (freq_word >= FREQUENCY_MIN_VALID && freq_word <= FREQUENCY_MAX_VALID) {
      ESP_LOGI(APC_HID_TAG, "Found frequency %.0f Hz using Method 3 (16-bit big-endian)", static_cast<float>(freq_word));
      return static_cast<float>(freq_word);
    }
  }
  
  // Method 4: Scaled frequency (multiply by 0.1 for devices reporting in 0.1 Hz units)
  if (report.data.size() >= 3) {
    uint16_t freq_scaled = report.data[1] | (report.data[2] << 8);
    float freq_value = static_cast<float>(freq_scaled) / battery::VOLTAGE_SCALE_FACTOR;
    ESP_LOGV(APC_HID_TAG, "Method 4 - Testing scaled frequency: raw=%d, scaled=%.1f - Range check: %s", 
             freq_scaled, freq_value,
             (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
    if (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID) {
      ESP_LOGI(APC_HID_TAG, "Found frequency %.1f Hz using Method 4 (scaled 0.1x)", freq_value);
      return freq_value;
    }
  }
  
  // Method 5: APC-specific frequency encoding - scale by 0.01 (some APC models use centihz)
  if (report.data.size() >= 3) {
    uint16_t freq_scaled = report.data[1] | (report.data[2] << 8);
    float freq_value = static_cast<float>(freq_scaled) / battery::MAX_LEVEL_PERCENT;
    ESP_LOGV(APC_HID_TAG, "Method 5 - Testing APC centihz frequency: raw=%d, scaled=%.2f - Range check: %s", 
             freq_scaled, freq_value,
             (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
    if (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID) {
      ESP_LOGI(APC_HID_TAG, "Found frequency %.2f Hz using Method 5 (APC centihz 0.01x)", freq_value);
      return freq_value;
    }
  }
  
  // Method 6: Try big-endian centihz scaling (some APC devices)
  if (report.data.size() >= 3) {
    uint16_t freq_scaled = (report.data[1] << 8) | report.data[2];
    float freq_value = static_cast<float>(freq_scaled) / battery::MAX_LEVEL_PERCENT;
    ESP_LOGV(APC_HID_TAG, "Method 6 - Testing APC big-endian centihz: raw=%d, scaled=%.2f - Range check: %s", 
             freq_scaled, freq_value,
             (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID) ? "PASS" : "FAIL");
    if (freq_value >= FREQUENCY_MIN_VALID && freq_value <= FREQUENCY_MAX_VALID) {
      ESP_LOGI(APC_HID_TAG, "Found frequency %.2f Hz using Method 6 (APC big-endian centihz)", freq_value);
      return freq_value;
    }
  }
  
  // Method 7: Check for frequency encoded in a different byte position (NUT shows various layouts)
  for (size_t i = 1; i < report.data.size(); i++) {
    if (report.data[i] == 50 || report.data[i] == 60) {
      ESP_LOGI(APC_HID_TAG, "Found exact frequency %d Hz at byte[%zu]", report.data[i], i);
      return static_cast<float>(report.data[i]);
    }
  }
  
  ESP_LOGD(APC_HID_TAG, "No valid frequency found in report 0x%02X (tried 7 methods)", report.data[0]);
  return NAN;
}

void ApcHidProtocol::detect_nominal_power_rating(const std::string& model_name, UpsData &data) {
  ESP_LOGD(APC_HID_TAG, "Detecting nominal power rating for model: \"%s\"", model_name.c_str());
  
  // APC Back-UPS ES Series Power Ratings (based on model identification)
  // Reference: APC product specifications and actual device testing
  
  // Convert model name to lowercase for case-insensitive matching
  std::string model_lower = model_name;
  std::transform(model_lower.begin(), model_lower.end(), model_lower.begin(), ::tolower);
  
  float nominal_power_watts = 0.0f;
  
  if (model_lower.find("back-ups es 350") != std::string::npos) {
    nominal_power_watts = 200.0f;  // 350VA ≈ 200W
  }
  else if (model_lower.find("back-ups es 425") != std::string::npos) {
    nominal_power_watts = 255.0f;  // 425VA ≈ 255W  
  }
  else if (model_lower.find("back-ups es 500") != std::string::npos) {
    nominal_power_watts = 300.0f;  // 500VA ≈ 300W
  }
  else if (model_lower.find("back-ups es 550") != std::string::npos) {
    nominal_power_watts = 330.0f;  // 550VA ≈ 330W
  }
  else if (model_lower.find("back-ups es 650") != std::string::npos) {
    nominal_power_watts = 390.0f;  // 650VA ≈ 390W
  }
  else if (model_lower.find("back-ups es 700") != std::string::npos || 
           model_lower.find("back-ups es 700g") != std::string::npos) {
    nominal_power_watts = 405.0f;  // 700VA ≈ 405W (confirmed from config)
  }
  else if (model_lower.find("back-ups es 750") != std::string::npos) {
    nominal_power_watts = 450.0f;  // 750VA ≈ 450W
  }
  else if (model_lower.find("back-ups es 850") != std::string::npos) {
    nominal_power_watts = 510.0f;  // 850VA ≈ 510W
  }
  else if (model_lower.find("back-ups es 900") != std::string::npos) {
    nominal_power_watts = 540.0f;  // 900VA ≈ 540W
  }
  else if (model_lower.find("back-ups es 1000") != std::string::npos) {
    nominal_power_watts = 600.0f;  // 1000VA ≈ 600W
  }
  else if (model_lower.find("back-ups es 1200") != std::string::npos) {
    nominal_power_watts = 720.0f;  // 1200VA ≈ 720W
  }
  else if (model_lower.find("back-ups es 1400") != std::string::npos) {
    nominal_power_watts = 840.0f;  // 1400VA ≈ 840W
  }
  
  // Generic fallback patterns for other APC Back-UPS models
  else if (model_lower.find("back-ups") != std::string::npos) {
    // Try to extract VA rating from model name (e.g., "Back-UPS 1500")
    std::regex va_pattern(R"(\b(\d{3,4})\b)");  // Match 3-4 digit numbers
    std::smatch match;
    if (std::regex_search(model_lower, match, va_pattern)) {
      int va_rating = std::stoi(match[1].str());
      // Typical APC power factor is ~0.6 for ES series, ~0.7 for higher-end
      if (model_lower.find(" es ") != std::string::npos) {
        nominal_power_watts = va_rating * 0.6f;  // ES series: lower power factor
      } else {
        nominal_power_watts = va_rating * 0.7f;  // Pro/Smart series: higher power factor
      }
      ESP_LOGD(APC_HID_TAG, "Extracted VA rating %d from model, calculated %0.1fW", va_rating, nominal_power_watts);
    }
  }
  
  // Set the nominal power if detected
  if (nominal_power_watts > 0.0f) {
    data.power.realpower_nominal = nominal_power_watts;
    ESP_LOGI(APC_HID_TAG, "Detected APC nominal power rating: %.1fW for model \"%s\"", 
             nominal_power_watts, model_name.c_str());
  } else {
    ESP_LOGW(APC_HID_TAG, "Could not determine nominal power rating for APC model: \"%s\"", model_name.c_str());
    // Don't set realpower_nominal - leave it as NaN so template sensors can handle gracefully
  }
}

bool ApcHidProtocol::read_timer_data(UpsData &data) {
  ESP_LOGD(APC_HID_TAG, "Reading APC timer countdown data");
  
  HidReport delay_shutdown_report;
  HidReport delay_reboot_report;
  bool success = false;
  
  // Read delay shutdown report to get the RAW timer value
  if (read_hid_report(APC_REPORT_ID_DELAY_SHUTDOWN, delay_shutdown_report)) {
    // Parse the delay configuration (this updates data.config.delay_shutdown)
    parse_ups_delay_shutdown_report(delay_shutdown_report, data);
    
    // Now read the RAW HID value to determine actual timer state
    // From NUT analysis: HID value -1 means timer inactive, positive values mean countdown active
    if (delay_shutdown_report.data.size() >= 3) {
      int16_t raw_timer_value = static_cast<int16_t>(
        delay_shutdown_report.data[1] | (delay_shutdown_report.data[2] << 8)
      );
      
      ESP_LOGD(APC_HID_TAG, "Raw timer shutdown HID value: %d", raw_timer_value);
      
      // Follow NUT convention: negative = inactive, positive = active countdown
      if (raw_timer_value == -1) {
        // Timer is inactive (normal operation)
        data.test.timer_shutdown = -1;
        ESP_LOGV(APC_HID_TAG, "Timer shutdown inactive (normal operation)");
      } else if (raw_timer_value > 0) {
        // Timer is actively counting down
        data.test.timer_shutdown = raw_timer_value;
        ESP_LOGI(APC_HID_TAG, "Timer shutdown ACTIVE countdown: %d seconds", raw_timer_value);
      } else {
        // Other negative values - treat as inactive but preserve the value
        data.test.timer_shutdown = raw_timer_value;
        ESP_LOGV(APC_HID_TAG, "Timer shutdown inactive: %d", raw_timer_value);
      }
    } else {
      // Fallback if report is too short
      data.test.timer_shutdown = -1;
      ESP_LOGW(APC_HID_TAG, "Timer shutdown report too short, assuming inactive");
    }
    success = true;
  }
  
  // Read delay reboot report to get the RAW timer value
  if (read_hid_report(APC_REPORT_ID_DELAY_REBOOT, delay_reboot_report)) {
    // Parse the delay configuration (this updates data.config.delay_reboot)
    parse_ups_delay_reboot_report(delay_reboot_report, data);
    
    // Read the RAW HID value for reboot timer
    if (delay_reboot_report.data.size() >= 2) {
      uint8_t raw_reboot_value = delay_reboot_report.data[1];
      
      ESP_LOGD(APC_HID_TAG, "Raw timer reboot HID value: %d", raw_reboot_value);
      
      // APC reboot timer: 0 typically means no reboot delay (immediate)
      if (raw_reboot_value == 0) {
        data.test.timer_reboot = -1; // Inactive (or immediate reboot)
        ESP_LOGV(APC_HID_TAG, "Timer reboot inactive (immediate/no delay)");
      } else {
        // Positive value indicates active reboot countdown
        data.test.timer_reboot = static_cast<int>(raw_reboot_value);
        ESP_LOGD(APC_HID_TAG, "Timer reboot countdown: %d seconds", raw_reboot_value);
      }
    } else {
      data.test.timer_reboot = -1;
      ESP_LOGW(APC_HID_TAG, "Timer reboot report too short, assuming inactive");
    }
    success = true;
  }
  
  // APC doesn't have a separate "start" timer - use reboot timer value
  data.test.timer_start = data.test.timer_reboot;
  
  if (success) {
    ESP_LOGD(APC_HID_TAG, "APC timer data updated - shutdown: %d, start: %d, reboot: %d",
             data.test.timer_shutdown, data.test.timer_start, data.test.timer_reboot);
  }
  
  return success;
}

// Delay configuration methods
bool ApcHidProtocol::set_shutdown_delay(int seconds) {
  ESP_LOGI(APC_HID_TAG, "Setting shutdown delay to %d seconds", seconds);
  
  // Validate range (0-600 seconds = 0-10 minutes for APC)
  if (seconds < 0 || seconds > 600) {
    ESP_LOGW(APC_HID_TAG, "Shutdown delay %d seconds out of range (0-600)", seconds);
    return false;
  }
  
  // Check if device supports SET_REPORT operations
  if (!parent_->is_connected()) {
    ESP_LOGW(APC_HID_TAG, "Cannot set shutdown delay - device not connected");
    return false;
  }
  
  // For APC Back-UPS ES 700G (INPUT-ONLY device), we need special handling
  // These devices don't have OUT endpoints and may not support SET_REPORT
  // We'll attempt control transfer anyway as it might work on some models
  
  // Prepare HID SET_REPORT data for shutdown delay
  // APC uses report 0x41 for delay before shutdown
  // Format: Report ID 0x41, 2 bytes little-endian seconds value
  uint8_t delay_data[2];
  delay_data[0] = seconds & 0xFF;           // Low byte
  delay_data[1] = (seconds >> 8) & 0xFF;    // High byte
  
  ESP_LOGD(APC_HID_TAG, "Writing shutdown delay: Report 0x%02X, Value: %d (0x%02X 0x%02X)", 
           APC_REPORT_ID_DELAY_SHUTDOWN, seconds, delay_data[0], delay_data[1]);
  
  // Attempt SET_REPORT via control transfer (works even on INPUT-ONLY devices sometimes)
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_DELAY_SHUTDOWN, 
                                         delay_data, 2, parent_->get_protocol_timeout());
  
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "Shutdown delay set successfully to %d seconds", seconds);
    return true;
  } else if (ret == ESP_ERR_NOT_SUPPORTED) {
    ESP_LOGW(APC_HID_TAG, "Device does not support delay configuration (INPUT-ONLY device)");
    ESP_LOGI(APC_HID_TAG, "Note: APC Back-UPS ES 700G is INPUT-ONLY and cannot be configured via USB");
    return false;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to set shutdown delay: %s", esp_err_to_name(ret));
    return false;
  }
}

bool ApcHidProtocol::set_start_delay(int seconds) {
  ESP_LOGI(APC_HID_TAG, "Setting start/reboot delay to %d seconds", seconds);
  
  // Validate range (0-600 seconds = 0-10 minutes for APC)
  if (seconds < 0 || seconds > 600) {
    ESP_LOGW(APC_HID_TAG, "Start delay %d seconds out of range (0-600)", seconds);
    return false;
  }
  
  // Check if device supports SET_REPORT operations
  if (!parent_->is_connected()) {
    ESP_LOGW(APC_HID_TAG, "Cannot set start delay - device not connected");
    return false;
  }
  
  // APC uses report 0x40 for reboot/start delay
  // Format: Report ID 0x40, 1 byte seconds value (limited to 255 seconds)
  uint8_t delay_data[1];
  delay_data[0] = std::min(seconds, 255);  // Limit to 255 for single byte
  
  ESP_LOGD(APC_HID_TAG, "Writing start/reboot delay: Report 0x%02X, Value: %d (0x%02X)", 
           APC_REPORT_ID_DELAY_REBOOT, delay_data[0], delay_data[0]);
  
  // Attempt SET_REPORT via control transfer
  esp_err_t ret = parent_->hid_set_report(HID_REPORT_TYPE_FEATURE, APC_REPORT_ID_DELAY_REBOOT, 
                                         delay_data, 1, parent_->get_protocol_timeout());
  
  if (ret == ESP_OK) {
    ESP_LOGI(APC_HID_TAG, "Start/reboot delay set successfully to %d seconds", delay_data[0]);
    return true;
  } else if (ret == ESP_ERR_NOT_SUPPORTED) {
    ESP_LOGW(APC_HID_TAG, "Device does not support delay configuration (INPUT-ONLY device)");
    return false;
  } else {
    ESP_LOGW(APC_HID_TAG, "Failed to set start/reboot delay: %s", esp_err_to_name(ret));
    return false;
  }
}

bool ApcHidProtocol::set_reboot_delay(int seconds) {
  // For APC, reboot delay is the same as start delay (report 0x40)
  return set_start_delay(seconds);
}

} // namespace ups_hid
} // namespace esphome

// Protocol Factory Self-Registration
#include "protocol_factory.h"

namespace esphome {
namespace ups_hid {

// Creator function for APC protocol
std::unique_ptr<UpsProtocolBase> create_apc_protocol(UpsHidComponent* parent) {
    return std::make_unique<ApcHidProtocol>(parent);
}

} // namespace ups_hid
} // namespace esphome

// Register APC protocol for vendor ID 0x051D
REGISTER_UPS_PROTOCOL_FOR_VENDOR(0x051D, apc_hid_protocol, esphome::ups_hid::create_apc_protocol, "APC HID Protocol", "APC Back-UPS and Smart-UPS HID protocol implementation with comprehensive sensor support", 100);