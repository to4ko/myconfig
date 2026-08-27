#pragma once

#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/component.h"

#include "esphome/components/climate/climate.h"

#include "../tion_component.h"

namespace esphome {
namespace tion {

class TionClimate : public climate::Climate, public Component, public Parented<TionApiComponent> {
  using TionState = dentra::tion::TionState;

 public:
  explicit TionClimate(TionApiComponent *api) : Parented(api) {}

  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }
  void dump_config() override;
  void setup() override;

  climate::ClimateTraits traits() override;
  void control(const climate::ClimateCall &call) override;

  void set_enable_heat_cool(bool enable_heat_cool) { this->enable_heat_cool_ = enable_heat_cool; }
  void set_enable_fan_auto(bool enable_fan_auto) { this->enable_fan_auto_ = enable_fan_auto; }

 protected:
  bool enable_heat_cool_{};
  bool enable_fan_auto_{};
  // Владеющее хранилище для строк, регистрируемых через
  // Climate::set_supported_custom_fan_modes()/set_supported_custom_presets():
  // указатели там не копируются, только сохраняются как const char*, и
  // обязаны жить всё время существования компонента (см. комментарий
  // "never freed - entity lives forever" в esphome/components/climate/climate.h).
  std::vector<std::string> custom_fan_modes_{};
  std::vector<std::string> custom_presets_{};
  void on_state_(const TionState &state);
  // важно this->mode уже должен быть выставлен в актуальное значение
  // отрицательное значение - автоматическая скорость вентиляции
  bool set_fan_speed_(int8_t fan_speed);
};

}  // namespace tion
}  // namespace esphome
