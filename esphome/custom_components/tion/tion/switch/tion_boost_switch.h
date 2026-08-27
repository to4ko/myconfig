#pragma once

#include "tion_switch.h"

namespace esphome {
namespace tion {

class TionBoostSwitch : public TionSwitch<property_controller::switch_::Boost> {
 public:
  explicit TionBoostSwitch(TionApiComponent *api) : TionSwitch(api) {}

  void set_boost_time(uint8_t boost_time) { property_controller::number::BoostTime::set(this->parent_, boost_time); }
  void set_boost_heater_state(bool heater_state) { this->api()->set_boost_heater_state(heater_state); }
  void set_boost_target_temperature(int8_t target_temperature) {
    this->api()->set_boost_target_temperature(target_temperature);
  }

 protected:
  dentra::tion::TionApiBase *api() const { return this->parent_->api(); }
};

}  // namespace tion
}  // namespace esphome
