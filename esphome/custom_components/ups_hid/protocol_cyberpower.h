#pragma once

#include "ups_hid.h"

namespace esphome {
namespace ups_hid {

/**
 * @brief CyberPower HID Protocol Implementation
 * 
 * Based on NUT cps-hid.c driver reference implementation.
 * Supports CP1500EPFCLCD and similar CyberPower models.
 * 
 * Key differences from APC:
 * - Different report IDs for core data
 * - Voltage scaling may be needed (2/3 factor)
 * - Frequency scaling (0.1 factor) for some models
 * - Uses Feature Reports for most data
 */
class CyberPowerProtocol : public UpsProtocolBase {
 public:
  CyberPowerProtocol(UpsHidComponent *parent) : UpsProtocolBase(parent) {}

  bool detect() override;
  bool initialize() override;
  bool read_data(UpsData &data) override;
  DeviceInfo::DetectedProtocol get_protocol_type() const override { return DeviceInfo::PROTOCOL_CYBERPOWER_HID; }
  std::string get_protocol_name() const override { return "CyberPower HID"; }
  
  // Beeper control methods
  bool beeper_enable() override;
  bool beeper_disable() override;
  bool beeper_mute() override;
  bool beeper_test() override;
  
  // UPS and battery test methods
  bool start_battery_test_quick() override;
  bool start_battery_test_deep() override;
  bool stop_battery_test() override;
  bool start_ups_test() override;
  bool stop_ups_test() override;
  
  // Timer polling for real-time countdown
  bool read_timer_data(UpsData &data) override;
  
  // Delay configuration methods
  bool set_shutdown_delay(int seconds) override;
  bool set_start_delay(int seconds) override;
  bool set_reboot_delay(int seconds) override;

 private:
  // Report ID constants (based on NUT debug logs)
  static const uint8_t BATTERY_CAPACITY_REPORT_ID = 0x07;  // Battery capacity limits
  static const uint8_t BATTERY_RUNTIME_REPORT_ID = 0x08;  // Battery % + Runtime
  static const uint8_t BATTERY_VOLTAGE_NOMINAL_REPORT_ID = 0x09;  // Battery voltage nominal
  static const uint8_t BATTERY_VOLTAGE_REPORT_ID = 0x0a;  // Battery voltage
  static const uint8_t PRESENT_STATUS_REPORT_ID = 0x0b;   // Status bitmap
  static const uint8_t BEEPER_STATUS_REPORT_ID = 0x0c;    // Beeper status
  static const uint8_t INPUT_VOLTAGE_NOMINAL_REPORT_ID = 0x0e;  // Input voltage nominal
  static const uint8_t INPUT_VOLTAGE_REPORT_ID = 0x0f;    // Input voltage  
  static const uint8_t INPUT_TRANSFER_REPORT_ID = 0x10;   // Input transfer limits
  static const uint8_t OUTPUT_VOLTAGE_REPORT_ID = 0x12;   // Output voltage
  static const uint8_t LOAD_PERCENT_REPORT_ID = 0x13;     // Load percentage
  static const uint8_t DELAY_SHUTDOWN_REPORT_ID = 0x15;   // Delay before shutdown
  static const uint8_t DELAY_START_REPORT_ID = 0x16;      // Delay before startup
  static const uint8_t OVERLOAD_REPORT_ID = 0x17;         // Overload status
  static const uint8_t REALPOWER_NOMINAL_REPORT_ID = 0x18; // Nominal real power
  static const uint8_t INPUT_SENSITIVITY_REPORT_ID = 0x1a; // Input sensitivity
  static const uint8_t FIRMWARE_VERSION_REPORT_ID = 0x1b;  // Firmware version
  // Note: Serial number report ID moved to shared constant usb::REPORT_ID_SERIAL_NUMBER
  static const uint8_t TEST_RESULT_REPORT_ID = 0x14;       // UPS test result (same as test command)

  // HID Report structure
  struct HidReport {
    uint8_t report_id;
    std::vector<uint8_t> data;
    
    HidReport() : report_id(0) {}
  };

  // CyberPower-specific scaling factors
  float battery_voltage_scale_ = 1.0f;
  bool battery_scale_checked_ = false;
  
  // HID communication methods
  bool read_hid_report(uint8_t report_id, HidReport &report);
  
  // Parser methods for different reports
  void parse_battery_capacity_report(const HidReport &report, UpsData &data);
  void parse_battery_runtime_report(const HidReport &report, UpsData &data);
  void parse_battery_voltage_report(const HidReport &report, UpsData &data); 
  void parse_battery_voltage_nominal_report(const HidReport &report, UpsData &data);
  void parse_present_status_report(const HidReport &report, UpsData &data);
  void parse_beeper_status_report(const HidReport &report, UpsData &data);
  void parse_input_voltage_nominal_report(const HidReport &report, UpsData &data);
  void parse_input_voltage_report(const HidReport &report, UpsData &data);
  void parse_input_transfer_report(const HidReport &report, UpsData &data);
  void parse_output_voltage_report(const HidReport &report, UpsData &data);
  void parse_load_percent_report(const HidReport &report, UpsData &data);
  void parse_delay_shutdown_report(const HidReport &report, UpsData &data);
  void parse_delay_start_report(const HidReport &report, UpsData &data);
  void parse_realpower_nominal_report(const HidReport &report, UpsData &data);
  void parse_overload_report(const HidReport &report, UpsData &data);
  void parse_input_sensitivity_report(const HidReport &report, UpsData &data);
  void parse_firmware_version_report(const HidReport &report, UpsData &data);
  void parse_serial_number_report(const HidReport &report, UpsData &data);
  void parse_test_result_report(const HidReport &report, UpsData &data);
  
  // Missing dynamic values from NUT analysis
  void read_missing_dynamic_values(UpsData &data);
  void parse_battery_capacity_limits_report(const HidReport &report, UpsData &data);
  void parse_battery_chemistry_report(const HidReport &report, UpsData &data);
  void parse_manufacturing_date_report(const HidReport &report, UpsData &data);
  
  // String cleaning utilities
  std::string clean_firmware_string(const std::string &raw_firmware);

  // CyberPower-specific scaling logic
  void check_battery_voltage_scaling(float battery_voltage, float nominal_voltage);
  
  // Frequency reading methods
  void read_frequency_data(UpsData &data);
  float parse_frequency_from_report(const HidReport &report);
};

}  // namespace ups_hid
}  // namespace esphome