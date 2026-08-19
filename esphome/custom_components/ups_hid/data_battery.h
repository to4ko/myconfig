#pragma once

#include <string>
#include <cmath>

namespace esphome {
namespace ups_hid {

struct BatteryData {
  // Core battery metrics
  float level{NAN};                    // Battery charge level (0-100%)
  float voltage{NAN};                  // Current battery voltage (V)
  float voltage_nominal{NAN};          // Nominal battery voltage (V)
  float runtime_minutes{NAN};          // Estimated runtime (minutes)
  
  // Battery thresholds
  float charge_low{NAN};               // Low battery threshold (%)
  float charge_warning{NAN};           // Warning battery threshold (%)
  float runtime_low{NAN};              // Low runtime threshold (minutes)
  
  // Battery status information
  std::string status{};                // Battery status text
  std::string type{};                  // Battery chemistry type
  std::string mfr_date{};              // Battery manufacture date
  
  // Validation and utility methods
  bool is_valid() const { 
    return !std::isnan(level) || !std::isnan(voltage) || !std::isnan(runtime_minutes);
  }
  
  bool is_low() const {
    return !std::isnan(level) && !std::isnan(charge_low) && level <= charge_low;
  }
  
  bool is_warning() const {
    return !std::isnan(level) && !std::isnan(charge_warning) && level <= charge_warning;
  }
  
  bool has_runtime_estimate() const {
    return !std::isnan(runtime_minutes) && runtime_minutes > 0;
  }
  
  void reset() { 
    *this = BatteryData{}; 
  }
  
  // Copy constructor and assignment for safe copying
  BatteryData() = default;
  BatteryData(const BatteryData&) = default;
  BatteryData& operator=(const BatteryData&) = default;
  BatteryData(BatteryData&&) = default;
  BatteryData& operator=(BatteryData&&) = default;
};

}  // namespace ups_hid
}  // namespace esphome