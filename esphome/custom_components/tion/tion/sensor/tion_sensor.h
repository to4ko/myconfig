#pragma once

#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/component.h"

#include "esphome/components/sensor/sensor.h"

#include "../tion_component.h"
#include "../tion_properties.h"

namespace esphome {
namespace tion {

// C - PropertyController
template<class C> class TionSensor : public sensor::Sensor, public Component, public Parented<TionApiComponent> {
  using TionState = dentra::tion::TionState;
  using PC = property_controller::Controller<C>;

  constexpr static const auto *TAG = "tion_sensor";

 public:
  explicit TionSensor(TionApiComponent *api) : Parented(api) {}

  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

  void dump_config() override {
    if (this->is_failed()) {
      return;
    }
    LOG_SENSOR("", "Tion Sensor", this);
  }

  void setup() override {
    ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

    if (!PC::is_supported(this)) {
      return;
    }
    this->parent_->add_on_state_callback([this](const TionState *state) {
      if (!PC::publish_state(this, state)) {
        // has_state_ приватен в ESPHome >= 2026.x, доступ только через
        // set_has_state()/has_state() (см. esphome/core/entity_base.h).
        // callback_ у Sensor не переименовывался, тут без изменений.
        this->set_has_state(false);
        this->callback_.call(NAN);
      }
    });
  }
};

}  // namespace tion
}  // namespace esphome
