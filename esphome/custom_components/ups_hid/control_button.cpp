#include "control_button.h"
#include "constants_ups.h"
#include "esphome/core/log.h"

namespace esphome {
namespace ups_hid {

static const char *const BUTTON_TAG = "ups_hid.button";

void UpsHidButton::dump_config() {
  ESP_LOGCONFIG(BUTTON_TAG, "UPS HID Button:");
  if (button_type_ == BUTTON_TYPE_BEEPER) {
    ESP_LOGCONFIG(BUTTON_TAG, "  Beeper action: %s", beeper_action_.c_str());
  } else if (button_type_ == BUTTON_TYPE_TEST) {
    ESP_LOGCONFIG(BUTTON_TAG, "  Test action: %s", test_action_.c_str());
  }
}

void UpsHidButton::press_action() {
  if (!parent_) {
    ESP_LOGE(BUTTON_TAG, log_messages::NO_PARENT_COMPONENT);
    return;
  }

  if (!parent_->is_connected()) {
    if (button_type_ == BUTTON_TYPE_BEEPER) {
      ESP_LOGW(BUTTON_TAG, "UPS not connected, cannot execute beeper action: %s", beeper_action_.c_str());
    } else {
      ESP_LOGW(BUTTON_TAG, "UPS not connected, cannot execute test action: %s", test_action_.c_str());
    }
    return;
  }

  // Get the current protocol from the parent component
  UpsData ups_data = parent_->get_ups_data();
  if (ups_data.device.detected_protocol == DeviceInfo::PROTOCOL_UNKNOWN) {
    ESP_LOGW(BUTTON_TAG, "UPS protocol not detected, cannot execute button action");
    return;
  }

  // Get the active protocol
  auto active_protocol = parent_->get_active_protocol();
  if (!active_protocol) {
    ESP_LOGE(BUTTON_TAG, "No active protocol available");
    return;
  }

  bool success = false;
  
  if (button_type_ == BUTTON_TYPE_BEEPER) {
    ESP_LOGI(BUTTON_TAG, "Executing beeper action: %s", beeper_action_.c_str());
    
    if (beeper_action_ == beeper::ACTION_ENABLE) {
      success = active_protocol->beeper_enable();
    } else if (beeper_action_ == beeper::ACTION_DISABLE) {
      success = active_protocol->beeper_disable();
    } else if (beeper_action_ == beeper::ACTION_MUTE) {
      success = active_protocol->beeper_mute();
    } else if (beeper_action_ == beeper::ACTION_TEST) {
      success = active_protocol->beeper_test();
    } else {
      ESP_LOGE(BUTTON_TAG, "Unknown beeper action: %s", beeper_action_.c_str());
      return;
    }

    if (success) {
      ESP_LOGI(BUTTON_TAG, "Beeper action '%s' executed successfully", beeper_action_.c_str());
    } else {
      ESP_LOGW(BUTTON_TAG, "Failed to execute beeper action: %s", beeper_action_.c_str());
    }
  } 
  else if (button_type_ == BUTTON_TYPE_TEST) {
    ESP_LOGI(BUTTON_TAG, "Executing test action: %s", test_action_.c_str());
    
    if (test_action_ == test::ACTION_BATTERY_QUICK) {
      success = active_protocol->start_battery_test_quick();
    } else if (test_action_ == test::ACTION_BATTERY_DEEP) {
      success = active_protocol->start_battery_test_deep();
    } else if (test_action_ == test::ACTION_BATTERY_STOP) {
      success = active_protocol->stop_battery_test();
    } else if (test_action_ == test::ACTION_UPS_TEST) {
      success = active_protocol->start_ups_test();
    } else if (test_action_ == test::ACTION_UPS_STOP) {
      success = active_protocol->stop_ups_test();
    } else {
      ESP_LOGE(BUTTON_TAG, "Unknown test action: %s", test_action_.c_str());
      return;
    }

    if (success) {
      ESP_LOGI(BUTTON_TAG, "Test action '%s' executed successfully", test_action_.c_str());
    } else {
      ESP_LOGW(BUTTON_TAG, "Failed to execute test action: %s", test_action_.c_str());
    }
  }
}

}  // namespace ups_hid
}  // namespace esphome