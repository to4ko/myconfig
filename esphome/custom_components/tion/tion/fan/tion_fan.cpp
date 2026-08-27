#include <set>
#include "esphome/core/log.h"

#include "tion_fan.h"

namespace esphome {
namespace tion {

static const char *const TAG = "tion_fan";

void TionFan::setup() {
  ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

  this->parent_->add_on_state_callback([this](const TionState *state) {
    if (state) {
      this->on_state_(*state);
    }
  });
}

fan::FanTraits TionFan::get_traits() {
  auto traits = fan::FanTraits(false, true, false, this->parent_->traits().max_fan_speed);
  if (this->parent_->api()->has_presets()) {
    traits.set_supported_preset_modes(this->parent_->api()->get_presets());
  }
  return traits;
}

void TionFan::dump_config() { LOG_FAN("", "Tion Fan", this); }

void TionFan::control(const fan::FanCall &call) {
  auto *tion = this->parent_->make_call();

  if (this->parent_->api()->has_presets()) {
    auto preset_mode = call.get_preset_mode();
    if (!preset_mode.empty()) {
      const auto &preset = preset_mode;
      ESP_LOGD(TAG, "Set preset %s", preset.c_str());
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
    if (this->preset_mode != this->parent_->api()->get_active_preset()) {
      this->preset_mode = this->parent_->api()->get_active_preset();
      has_changes = true;
    }
  }

  if (this->parent_->get_force_update() || has_changes) {
    this->publish_state();
  }
}

}  // namespace tion
}  // namespace esphome
