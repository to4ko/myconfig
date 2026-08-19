#pragma once

#include "esphome/core/component.h"
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

}  // namespace ups_hid
}  // namespace esphome