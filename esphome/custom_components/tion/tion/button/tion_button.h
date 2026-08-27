#pragma once

#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/component.h"
#include "esphome/core/log.h"

#include "esphome/components/button/button.h"

#include "../tion_component.h"
#include "../tion_properties.h"

namespace esphome {
namespace tion {

// C - PropertyController
template<class C> class TionButton : public button::Button, public Component, public Parented<TionApiComponent> {
 protected:
  using TionState = dentra::tion::TionState;
  using PC = property_controller::Controller<C>;

  constexpr static const auto *TAG = "tion_button";

 public:
  explicit TionButton(TionApiComponent *api) : Parented(api) {}

  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

  void dump_config() override {
    if (this->is_failed()) {
      return;
    }
    LOG_BUTTON("", "Tion Button", this);
  }

  void setup() override {
    ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

    if (!C::is_supported(this->parent_)) {
      PC::mark_unsupported(this);
      return;
    }
  }

 protected:
  void press_action() override { C::press_action(this->parent_); }
};

}  // namespace tion
}  // namespace esphome
