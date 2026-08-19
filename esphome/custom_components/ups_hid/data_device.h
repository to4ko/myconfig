#pragma once

#include <string>

namespace esphome {
namespace ups_hid {

struct DeviceInfo {
  // Basic device identification
  std::string manufacturer{};          // Device manufacturer
  std::string model{};                 // Device model name
  std::string serial_number{};         // Device serial number
  std::string firmware_version{};      // Primary firmware version
  std::string firmware_aux{};          // Auxiliary firmware info
  std::string mfr_date{};              // Device manufacture date
  
  // USB device identification
  uint16_t usb_vendor_id{0};          // USB Vendor ID
  uint16_t usb_product_id{0};         // USB Product ID
  
  // Protocol information
  enum DetectedProtocol {
    PROTOCOL_UNKNOWN = 0,
    PROTOCOL_APC_HID,
    PROTOCOL_CYBERPOWER_HID,
    PROTOCOL_GENERIC_HID,
    PROTOCOL_MEGATEC_Q1
  };
  
  DetectedProtocol detected_protocol{PROTOCOL_UNKNOWN};
  
  // Device capabilities flags
  struct Capabilities {
    bool supports_hid_get_report{false};
    bool supports_hid_set_report{false};
    bool supports_beeper_control{false};
    bool supports_battery_test{false};
    bool supports_ups_test{false};
    bool is_input_only_device{false};
    bool supports_runtime_estimation{false};
    bool supports_configuration_queries{false};
  };
  
  Capabilities capabilities{};
  
  // Validation and utility methods
  bool is_valid() const {
    return !manufacturer.empty() || !model.empty() || !serial_number.empty();
  }
  
  bool has_basic_info() const {
    return !manufacturer.empty() && !model.empty();
  }
  
  bool has_usb_info() const {
    return usb_vendor_id != 0;
  }
  
  std::string get_protocol_name() const {
    switch (detected_protocol) {
      case PROTOCOL_APC_HID: return "APC HID";
      case PROTOCOL_CYBERPOWER_HID: return "CyberPower HID";
      case PROTOCOL_GENERIC_HID: return "Generic HID";
      case PROTOCOL_MEGATEC_Q1: return "Megatec/Q1 (Cypress)";
      default: return "Unknown";
    }
  }
  
  std::string get_device_description() const {
    if (has_basic_info()) {
      return manufacturer + " " + model;
    } else if (!model.empty()) {
      return model;
    } else if (!manufacturer.empty()) {
      return manufacturer + " Device";
    } else {
      return "Unknown UPS";
    }
  }
  
  std::string get_usb_description() const {
    if (has_usb_info()) {
      char buffer[32];
      snprintf(buffer, sizeof(buffer), "0x%04X:0x%04X", usb_vendor_id, usb_product_id);
      return std::string(buffer);
    }
    return "Unknown USB ID";
  }
  
  void reset() { 
    *this = DeviceInfo{}; 
  }
  
  // Copy constructor and assignment for safe copying
  DeviceInfo() = default;
  DeviceInfo(const DeviceInfo&) = default;
  DeviceInfo& operator=(const DeviceInfo&) = default;
  DeviceInfo(DeviceInfo&&) = default;
  DeviceInfo& operator=(DeviceInfo&&) = default;
};

}  // namespace ups_hid
}  // namespace esphome