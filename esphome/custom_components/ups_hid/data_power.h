#pragma once

#include <string>
#include <cmath>
#include "constants_hid.h"

namespace esphome {
namespace ups_hid {

struct PowerData {
  // Input power metrics
  float input_voltage{NAN};            // Current input voltage (V)
  float input_voltage_nominal{NAN};    // Nominal input voltage (V)
  float input_transfer_low{NAN};       // Low transfer voltage threshold (V)
  float input_transfer_high{NAN};      // High transfer voltage threshold (V)
  float frequency{NAN};                // Input frequency (Hz)
  
  // Output power metrics
  float output_voltage{NAN};           // Current output voltage (V)
  float output_voltage_nominal{NAN};   // Nominal output voltage (V)
  float load_percent{NAN};             // Current load percentage (0-100%)
  
  // Power ratings and capabilities
  float realpower_nominal{NAN};        // Nominal real power rating (W)
  float apparent_power_nominal{NAN};   // Nominal apparent power rating (VA)
  
  // Power status information
  std::string status{};                // Power status text (Online, On Battery, etc.)

  // Authoritative online/on-battery state, when the protocol can report it
  // directly (e.g. Megatec/Q1's status byte bit 7 "Utility Fail"). When
  // on_battery_known is false, callers should fall back to inferring
  // online/on-battery from input_voltage_valid() instead, since not every
  // protocol/device reliably reports a dedicated bit for this - some
  // simply keep echoing the last-seen input voltage even while running on
  // battery, which would make the voltage-based heuristic wrong.
  bool on_battery_known{false};
  bool on_battery{false};
  
  // Power quality indicators
  bool input_voltage_valid() const {
    return !std::isnan(input_voltage) && input_voltage > 50.0f && input_voltage < 300.0f;
  }
  
  bool output_voltage_valid() const {
    return !std::isnan(output_voltage) && output_voltage > 50.0f && output_voltage < 300.0f;
  }
  
  bool frequency_valid() const {
    return !std::isnan(frequency) && frequency >= FREQUENCY_MIN_VALID && frequency <= FREQUENCY_MAX_VALID;
  }
  
  bool is_input_out_of_range() const {
    if (!input_voltage_valid()) return false;
    return (!std::isnan(input_transfer_low) && input_voltage < input_transfer_low) ||
           (!std::isnan(input_transfer_high) && input_voltage > input_transfer_high);
  }
  
  bool is_overloaded() const {
    return !std::isnan(load_percent) && load_percent > 95.0f;
  }
  
  bool has_load_info() const {
    return !std::isnan(load_percent);
  }
  
  // Validation and utility methods
  bool is_valid() const {
    return input_voltage_valid() || output_voltage_valid() || has_load_info();
  }
  
  void reset() { 
    *this = PowerData{}; 
  }
  
  // Copy constructor and assignment for safe copying
  PowerData() = default;
  PowerData(const PowerData&) = default;
  PowerData& operator=(const PowerData&) = default;
  PowerData(PowerData&&) = default;
  PowerData& operator=(PowerData&&) = default;
};

}  // namespace ups_hid
}  // namespace esphome