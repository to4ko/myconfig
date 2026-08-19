#pragma once

#include <string>
#include <cstdint>

namespace esphome {
namespace ups_hid {

struct ConfigData {
  // Timing configuration
  int16_t delay_shutdown{-1};          // Shutdown delay (seconds, -1 = not set)
  int16_t delay_start{-1};             // Start delay (seconds, -1 = not set)
  int16_t delay_reboot{-1};            // Reboot delay (seconds, -1 = not set)
  
  // Beeper configuration
  std::string beeper_status{};         // Current beeper status
  
  enum BeeperState {
    BEEPER_UNKNOWN = 0,
    BEEPER_ENABLED,
    BEEPER_DISABLED,
    BEEPER_MUTED
  };
  
  BeeperState beeper_state{BEEPER_UNKNOWN};
  
  // Input sensitivity configuration
  std::string input_sensitivity{};     // Input sensitivity setting
  
  enum SensitivityLevel {
    SENSITIVITY_UNKNOWN = 0,
    SENSITIVITY_LOW,
    SENSITIVITY_MEDIUM,
    SENSITIVITY_HIGH,
    SENSITIVITY_AUTO
  };
  
  SensitivityLevel sensitivity_level{SENSITIVITY_UNKNOWN};
  
  // Power management thresholds (configurable on some UPS models)
  float low_battery_threshold{NAN};    // Low battery warning threshold (%)
  float critical_battery_threshold{NAN}; // Critical battery threshold (%)
  float high_temperature_threshold{NAN}; // High temperature warning (°C)
  
  // Advanced configuration options
  bool auto_restart_enabled{false};    // Auto restart after power restoration
  bool cold_start_enabled{false};      // Cold start capability
  bool audible_alarm_enabled{true};    // Audible alarm on events
  
  // Communication settings
  uint16_t protocol_timeout_ms{15000}; // Protocol communication timeout
  uint16_t retry_count{3};             // Number of communication retries
  bool auto_detect_protocol{true};     // Automatic protocol detection
  
  // Validation and utility methods
  bool has_timing_config() const {
    return delay_shutdown != -1 || delay_start != -1 || delay_reboot != -1;
  }
  
  bool has_beeper_config() const {
    return !beeper_status.empty() || beeper_state != BEEPER_UNKNOWN;
  }
  
  bool has_sensitivity_config() const {
    return !input_sensitivity.empty() || sensitivity_level != SENSITIVITY_UNKNOWN;
  }
  
  bool has_thresholds() const {
    return !std::isnan(low_battery_threshold) || 
           !std::isnan(critical_battery_threshold) ||
           !std::isnan(high_temperature_threshold);
  }
  
  std::string get_beeper_state_name() const {
    switch (beeper_state) {
      case BEEPER_ENABLED: return "Enabled";
      case BEEPER_DISABLED: return "Disabled";
      case BEEPER_MUTED: return "Muted";
      default: return "Unknown";
    }
  }
  
  std::string get_sensitivity_name() const {
    switch (sensitivity_level) {
      case SENSITIVITY_LOW: return "Low";
      case SENSITIVITY_MEDIUM: return "Medium";
      case SENSITIVITY_HIGH: return "High";
      case SENSITIVITY_AUTO: return "Auto";
      default: return "Unknown";
    }
  }
  
  void parse_beeper_status(const std::string& status) {
    beeper_status = status;
    
    // Convert string to enum for easier handling
    if (status == "enabled" || status == "on" || status == "1") {
      beeper_state = BEEPER_ENABLED;
    } else if (status == "disabled" || status == "off" || status == "0") {
      beeper_state = BEEPER_DISABLED;
    } else if (status == "muted") {
      beeper_state = BEEPER_MUTED;
    } else {
      beeper_state = BEEPER_UNKNOWN;
    }
  }
  
  void parse_input_sensitivity(const std::string& sensitivity) {
    input_sensitivity = sensitivity;
    
    // Convert string to enum for easier handling
    if (sensitivity == "low" || sensitivity == "L") {
      sensitivity_level = SENSITIVITY_LOW;
    } else if (sensitivity == "medium" || sensitivity == "M" || sensitivity == "normal") {
      sensitivity_level = SENSITIVITY_MEDIUM;
    } else if (sensitivity == "high" || sensitivity == "H") {
      sensitivity_level = SENSITIVITY_HIGH;
    } else if (sensitivity == "auto" || sensitivity == "A") {
      sensitivity_level = SENSITIVITY_AUTO;
    } else {
      sensitivity_level = SENSITIVITY_UNKNOWN;
    }
  }
  
  bool is_beeper_enabled() const {
    return beeper_state == BEEPER_ENABLED;
  }
  
  bool is_beeper_muted() const {
    return beeper_state == BEEPER_MUTED;
  }
  
  bool is_valid() const {
    return has_timing_config() || has_beeper_config() || has_sensitivity_config() || has_thresholds();
  }
  
  void reset() { 
    *this = ConfigData{}; 
  }
  
  // Copy constructor and assignment for safe copying
  ConfigData() = default;
  ConfigData(const ConfigData&) = default;
  ConfigData& operator=(const ConfigData&) = default;
  ConfigData(ConfigData&&) = default;
  ConfigData& operator=(ConfigData&&) = default;
};

}  // namespace ups_hid
}  // namespace esphome