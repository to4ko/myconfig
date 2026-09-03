#pragma once

#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "esphome/components/number/number.h"
#include "ups_hid.h"

namespace esphome {
namespace ups_hid {

enum DelayType {
  DELAY_SHUTDOWN,
  DELAY_START,
  DELAY_REBOOT,
};

class UpsDelayNumber : public number::Number, public Component {
 public:
  void setup() override;
  void dump_config() override;
  
  void set_parent(UpsHidComponent *parent) { this->parent_ = parent; }
  void set_delay_type(DelayType type) { this->delay_type_ = type; }
  
  // Called when user changes the number value
  void control(float value) override;
  
  // Update the displayed value from UPS data
  void update_value(float value);
  
 protected:
  UpsHidComponent *parent_{nullptr};
  DelayType delay_type_;
  
  const char *delay_type_to_string() const;
};

enum CalibrationType {
  BATTERY_VOLTAGE_HIGH,
  BATTERY_VOLTAGE_LOW,
};

// Live-tunable battery percentage calibration point (0% or 100% voltage).
// Unlike UpsDelayNumber, this never talks to the UPS over USB - it's a
// purely local value that feeds back into the component's own
// battery-percentage estimate (see protocol_megatec.cpp's
// estimate_battery_level_percent()), so control() always "succeeds"
// immediately with no device round-trip.
class UpsCalibrationNumber : public number::Number, public Component {
 public:
  void setup() override;
  void dump_config() override;

  void set_parent(UpsHidComponent *parent) { this->parent_ = parent; }
  void set_calibration_type(CalibrationType type) { this->calibration_type_ = type; }

  void control(float value) override;

 protected:
  UpsHidComponent *parent_{nullptr};
  CalibrationType calibration_type_;
  // Persists the user-tuned value across reboots - without this, the
  // ups_hid: component's YAML-configured default would silently overwrite
  // whatever was set via this entity on every boot.
  ESPPreferenceObject pref_;

  const char *calibration_type_to_string() const;
};

}  // namespace ups_hid
}  // namespace esphome