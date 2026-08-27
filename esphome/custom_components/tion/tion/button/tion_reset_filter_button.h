#pragma once

#ifdef USE_SWITCH
#include "esphome/components/switch/switch.h"
#endif

#include "tion_button.h"

namespace esphome {
namespace tion {

class TionResetFilterButton : public TionButton<property_controller::button::ResetFilter> {
 public:
  explicit TionResetFilterButton(TionApiComponent *api) : TionButton(api) {}
#ifdef USE_SWITCH

  void setup() override {
    TionButton::setup();
    if (this->is_failed()) {
      if (this->confirm_) {
        PC::mark_unsupported_entity(this->confirm_);
      }
      return;
    }
  }

  void set_confirm(switch_::Switch *confirm) {
#ifndef TION_SPRUTHUB_SUPPORT
    this->confirm_ = confirm;
#endif
  }

 protected:
  switch_::Switch *confirm_{};

  void press_action() override {
    if (this->confirm_ == nullptr || this->confirm_->state) {
      TionButton::press_action();
    }
  }
#endif  // USE_SWITCH
};

#ifdef USE_SWITCH

template<class parent_t> class TionResetFilterConfirmSwitch : public Parented<parent_t>, public switch_::Switch {
  static_assert(std::is_base_of_v<Component, parent_t>, "parent_t is not Component");

 public:
  explicit TionResetFilterConfirmSwitch(parent_t *parent) : Parented<parent_t>(parent) {}
  void write_state(bool state) override {
    constexpr const char *timeout_name = "tion_reset_confirm_timeout";
    if (state) {
      App.scheduler.set_timeout(this->parent_, timeout_name, 10000, [this]() { this->publish_state(false); });
    } else {
      App.scheduler.cancel_timeout(this->parent_, timeout_name);
    }
    this->publish_state(state);
  }
};
#endif  // USE_SWITCH

}  // namespace tion
}  // namespace esphome
