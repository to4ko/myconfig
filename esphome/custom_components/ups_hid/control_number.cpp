#include "control_number.h"
#include "esphome/core/log.h"

namespace esphome {
namespace ups_hid {

static const char *const TAG_NUMBER = "ups_hid.number";

void UpsDelayNumber::setup() {
  ESP_LOGD(TAG_NUMBER, "Setting up UPS delay number '%s' for %s", 
           this->get_name().c_str(), this->delay_type_to_string());
}

void UpsDelayNumber::dump_config() {
  LOG_NUMBER("", "UPS Delay Number", this);
  ESP_LOGCONFIG(TAG_NUMBER, "  Type: %s", this->delay_type_to_string());
}

void UpsDelayNumber::control(float value) {
  ESP_LOGI(TAG_NUMBER, "Setting %s delay to %.0f seconds", this->delay_type_to_string(), value);
  
  if (this->parent_ == nullptr) {
    ESP_LOGW(TAG_NUMBER, "Parent UPS HID component not set");
    return;
  }
  
  // Call parent to set the delay value via USB HID
  bool success = false;
  switch (this->delay_type_) {
    case DELAY_SHUTDOWN:
      success = this->parent_->set_shutdown_delay(static_cast<int>(value));
      break;
    case DELAY_START:
      success = this->parent_->set_start_delay(static_cast<int>(value));
      break;
    case DELAY_REBOOT:
      success = this->parent_->set_reboot_delay(static_cast<int>(value));
      break;
  }
  
  if (success) {
    // Update displayed value if write succeeded
    this->publish_state(value);
    ESP_LOGI(TAG_NUMBER, "%s delay set successfully to %.0f seconds", 
             this->delay_type_to_string(), value);
  } else {
    ESP_LOGW(TAG_NUMBER, "Failed to set %s delay", this->delay_type_to_string());
    // Optionally refresh from device to show actual value
    this->parent_->request_delay_refresh();
  }
}

void UpsDelayNumber::update_value(float value) {
  if (!std::isnan(value) && this->state != value) {
    this->publish_state(value);
  }
}

const char *UpsDelayNumber::delay_type_to_string() const {
  switch (this->delay_type_) {
    case DELAY_SHUTDOWN:
      return "shutdown";
    case DELAY_START:
      return "start";
    case DELAY_REBOOT:
      return "reboot";
    default:
      return "unknown";
  }
}

}  // namespace ups_hid
}  // namespace esphome