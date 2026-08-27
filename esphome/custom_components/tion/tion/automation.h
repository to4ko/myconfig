#pragma once

#include "esphome/core/automation.h"
#include "tion_component.h"

namespace esphome {
namespace tion {

class StateTrigger : public Trigger<const dentra::tion::TionState &> {
 public:
  explicit StateTrigger(TionApiComponent *api) {
    api->add_on_state_callback([this](const auto *state) {
      if (state) {
        this->trigger(*state);
      }
    });
  }
};

}  // namespace tion
}  // namespace esphome
