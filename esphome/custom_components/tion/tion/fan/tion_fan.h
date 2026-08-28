#pragma once

#include <string>
#include <vector>

#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/component.h"

#include "esphome/components/fan/fan.h"

#include "../tion_component.h"

namespace esphome {
namespace tion {

class TionFan : public fan::Fan, public Component, public Parented<TionApiComponent> {
  using TionState = dentra::tion::TionState;

 public:
  explicit TionFan(TionApiComponent *api) : Parented(api) {}

  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }
  void dump_config() override;
  void setup() override;

  fan::FanTraits get_traits() override;

 protected:
  void control(const fan::FanCall &call) override;
  void on_state_(const TionState &state);

  // fan::Fan::set_supported_preset_modes() (ESPHome >= 2026.x) хранит не копии строк, а голые
  // const char*, обязанные жить вечно - поэтому исходные строки держим тут (см. tion_climate.h
  // custom_fan_modes_/custom_presets_ для того же паттерна).
  std::vector<std::string> preset_modes_storage_{};
};

}  // namespace tion
}  // namespace esphome
