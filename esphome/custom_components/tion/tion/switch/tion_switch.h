#pragma once

#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/component.h"
#include "esphome/core/log.h"

#include "esphome/components/switch/switch.h"

#include "../tion_component.h"
#include "../tion_properties.h"

namespace esphome {
namespace tion {

// C - PropertyController
template<class C> class TionSwitch : public switch_::Switch, public Component, public Parented<TionApiComponent> {
  friend class property_controller::Controller<C>;

  constexpr static const auto *TAG = "tion_switch";

 protected:
  using TionState = dentra::tion::TionState;
  using PC = property_controller::Controller<C>;

 public:
  explicit TionSwitch(TionApiComponent *api) : Parented(api) {}

  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

  void dump_config() override {
    if (this->is_failed()) {
      return;
    }
    LOG_SWITCH("", "Tion Switch", this);
  }

  void setup() override {
    ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

    if (!PC::is_supported(this)) {
      return;
    }
    this->parent_->add_on_state_callback(
        [this](const TionState *state) { this->has_state_ = PC::publish_state(this, state); });
  }

  bool assumed_state() override { return this->is_failed(); }

  bool has_state() const { return this->has_state_; }

  dentra::tion::TionApiBase *api() const { return this->parent_->api(); }

 protected:
  bool has_state_{};

  void write_state(bool state) override { PC::control(this, state); }
};

}  // namespace tion
}  // namespace esphome
