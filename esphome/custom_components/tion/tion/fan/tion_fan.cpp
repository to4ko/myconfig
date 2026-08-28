#include <set>
#include "esphome/core/log.h"

#include "tion_fan.h"

namespace esphome {
namespace tion {

static const char *const TAG = "tion_fan";

void TionFan::setup() {
  ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

  // fan::FanTraits::set_supported_preset_modes() помечен ESPDEPRECATED в ESPHome >= 2026.x
  // (удаляется в 2026.11.0); теперь пресеты регистрируются один раз на самой Fan-сущности
  // через set_supported_preset_modes(), а traits() просто ссылается на них через
  // wire_preset_modes_() (см. get_traits() ниже) - тот же паттерн, что и в tion_climate.cpp
  // для custom_fan_modes_/custom_presets_.
  if (this->parent_->api()->has_presets()) {
    for (auto &&preset : this->parent_->api()->get_presets()) {
      this->preset_modes_storage_.push_back(preset);
    }
    if (!this->preset_modes_storage_.empty()) {
      std::vector<const char *> modes;
      modes.reserve(this->preset_modes_storage_.size());
      for (const auto &mode : this->preset_modes_storage_) {
        modes.push_back(mode.c_str());
      }
      this->set_supported_preset_modes(modes);
    }
  }

  this->parent_->add_on_state_callback([this](const TionState *state) {
    if (state) {
      this->on_state_(*state);
    }
  });
}

fan::FanTraits TionFan::get_traits() {
  auto traits = fan::FanTraits(false, true, false, this->parent_->traits().max_fan_speed);
  // Подключает пресеты, зарегистрированные в setup() через set_supported_preset_modes(),
  // к traits (нужно для FanCall::set_preset_mode()/dump_traits_() - см. fan.cpp Fan::wire_preset_modes_()).
  this->wire_preset_modes_(traits);
  return traits;
}

void TionFan::dump_config() { LOG_FAN("", "Tion Fan", this); }

void TionFan::control(const fan::FanCall &call) {
  auto *tion = this->parent_->make_call();

  if (this->parent_->api()->has_presets()) {
    // FanCall::get_preset_mode() в ESPHome >= 2026.x возвращает const char* (не std::string),
    // поэтому проверяем has_preset_mode(), а не .empty() на несуществующем методе.
    if (call.has_preset_mode()) {
      const char *preset = call.get_preset_mode();
      ESP_LOGD(TAG, "Set preset %s", preset);
      this->parent_->api()->enable_preset(preset, tion);
    }
  }

  if (call.get_state().has_value()) {
    const auto state = *call.get_state();
    ESP_LOGD(TAG, "Set state %s", ONOFF(state));
    tion->set_power_state(state);
  }

  if (call.get_speed().has_value()) {
    const auto fan_speed = *call.get_speed();
    ESP_LOGD(TAG, "Set speed %u", fan_speed);
    tion->set_fan_speed(fan_speed);
  }

  tion->perform();
}

void TionFan::on_state_(const TionState &state) {
  bool has_changes = false;
  if (this->state != state.power_state) {
    this->state = state.power_state;
    has_changes = true;
  }
  if (this->speed != state.fan_speed) {
    this->speed = state.fan_speed;
    has_changes = true;
  }

  if (this->parent_->api()->has_presets()) {
    // preset_mode больше не публичное поле Fan (ESPHome >= 2026.x): чтение через
    // get_preset_mode() (StringRef), установка через set_preset_mode_() (см. tion_climate.cpp
    // тот же паттерн для custom_preset).
    const auto active_preset = this->parent_->api()->get_active_preset();
    if (this->get_preset_mode() != active_preset) {
      if (this->set_preset_mode_(active_preset.c_str())) {
        has_changes = true;
      }
    }
  }

  if (this->parent_->get_force_update() || has_changes) {
    this->publish_state();
  }
}

}  // namespace tion
}  // namespace esphome
