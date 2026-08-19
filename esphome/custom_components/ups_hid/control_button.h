#pragma once

#include "esphome/core/component.h"
#include "esphome/components/button/button.h"
#include "ups_hid.h"

namespace esphome {
namespace ups_hid {

enum UpsHidBeeperAction {
  UPS_HID_BEEPER_ENABLE,
  UPS_HID_BEEPER_DISABLE,
  UPS_HID_BEEPER_MUTE,
  UPS_HID_BEEPER_TEST
};

enum UpsHidTestAction {
  UPS_HID_TEST_BATTERY_QUICK,
  UPS_HID_TEST_BATTERY_DEEP,
  UPS_HID_TEST_BATTERY_STOP,
  UPS_HID_TEST_UPS_TEST,
  UPS_HID_TEST_UPS_STOP
};

class UpsHidButton : public button::Button, public Component {
 public:
  void set_ups_hid_parent(UpsHidComponent *parent) { parent_ = parent; }
  void set_beeper_action(const std::string &action) { beeper_action_ = action; button_type_ = BUTTON_TYPE_BEEPER; }
  void set_test_action(const std::string &action) { test_action_ = action; button_type_ = BUTTON_TYPE_TEST; }
  
  void dump_config() override;

 protected:
  void press_action() override;
  
  enum ButtonType {
    BUTTON_TYPE_BEEPER,
    BUTTON_TYPE_TEST
  };
  
  UpsHidComponent *parent_{nullptr};
  std::string beeper_action_{};
  std::string test_action_{};
  ButtonType button_type_{BUTTON_TYPE_BEEPER};
};

}  // namespace ups_hid
}  // namespace esphome