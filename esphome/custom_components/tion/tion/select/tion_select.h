#pragma once

#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/component.h"
#include "esphome/core/log.h"

#include "esphome/components/select/select.h"

#include "../tion_component.h"
#include "../tion_properties.h"

namespace esphome {
namespace tion {

// C - PropertyController
template<class C> class TionSelect : public select::Select, public Component, public Parented<TionApiComponent> {
  using TionState = dentra::tion::TionState;
  using PC = property_controller::Controller<C>;
  constexpr static const auto *TAG = "tion_select";

 public:
  explicit TionSelect(TionApiComponent *api) : Parented(api) {}

  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

  void dump_config() override {
    if (this->is_failed()) {
      return;
    }
    LOG_SELECT("", "Tion Select", this);
  }

  void setup() override {
    ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

    const auto options = C::get_options(this->parent_);
    if (options.size() != this->traits.get_options().size()) {
      this->traits.set_options(options);
    }
    if (this->traits.get_options().empty()) {
      PC::mark_unsupported(this);
      return;
    }
    ESP_LOGD(TAG, "Available options are:");
    for (auto &&opt : options) {
      ESP_LOGD(TAG, "  '%s'", opt.c_str());
    }
    this->parent_->add_on_state_callback([this](const TionState *state) {
      if (state) {
        if constexpr (PC::checker().has_api_get()) {
          this->internal_publish_state_(C::get(this->parent_));
        } else {
          this->internal_publish_state_(C::get(*state, this->traits.get_options()));
        }
      } else {
        // has_state_ приватен в ESPHome >= 2026.x, доступ только через
        // set_has_state()/has_state() (см. esphome/core/entity_base.h).
        this->set_has_state(false);
      }
    });
  }

 protected:
  void internal_publish_state_(const std::string &st) {
    if (this->parent_->get_force_update() || !this->has_state() || st != this->state) {
      this->publish_state(st);
    }
  }
  void control(const std::string &value) override {
    if (this->is_failed()) {
      PC::report_unsupported(this);
      return;
    }
    auto *call = this->parent_->make_call();
    if constexpr (PC::checker().has_api_state_set()) {
      C::set(this->parent_, call, value);
    } else {
      C::set(call, value, this->traits.get_options());
    }
    call->perform();
  }
};

}  // namespace tion
}  // namespace esphome
