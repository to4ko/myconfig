#include "control_number.h"
#include "esphome/core/log.h"
#include <cmath>

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

void UpsCalibrationNumber::setup() {
  ESP_LOGD(TAG_NUMBER, "Setting up UPS calibration number '%s' for %s",
           this->get_name().c_str(), this->calibration_type_to_string());

  if (this->parent_ == nullptr) {
    ESP_LOGW(TAG_NUMBER, "Parent UPS HID component not set");
    return;
  }

  // Salted so this doesn't collide with some other component's preference
  // that happens to share this entity's object_id hash.
  this->pref_ = global_preferences->make_preference<float>(this->get_object_id_hash() ^ 0xCA71B4A7UL);

  float restored = NAN;
  if (this->pref_.load(&restored) && !std::isnan(restored)) {
    // A value was previously set via this entity (HA/web UI) - it wins
    // over the YAML default, which would otherwise silently clobber it on
    // every boot.
    if (this->calibration_type_ == BATTERY_VOLTAGE_HIGH) {
      this->parent_->set_battery_voltage_high_override(restored);
    } else {
      this->parent_->set_battery_voltage_low_override(restored);
    }
    this->publish_state(restored);
    return;
  }

  // Nothing persisted yet (first boot) - show whatever's currently in
  // effect (the YAML-configured default, if any was set on the ups_hid:
  // component) as this entity's starting state.
  float current = (this->calibration_type_ == BATTERY_VOLTAGE_HIGH)
                       ? this->parent_->get_battery_voltage_high_override()
                       : this->parent_->get_battery_voltage_low_override();
  if (!std::isnan(current)) {
    this->publish_state(current);
  }
}

void UpsCalibrationNumber::dump_config() {
  LOG_NUMBER("", "UPS Calibration Number", this);
  ESP_LOGCONFIG(TAG_NUMBER, "  Type: %s", this->calibration_type_to_string());
}

void UpsCalibrationNumber::control(float value) {
  if (this->parent_ == nullptr) {
    ESP_LOGW(TAG_NUMBER, "Parent UPS HID component not set");
    return;
  }

  switch (this->calibration_type_) {
    case BATTERY_VOLTAGE_HIGH:
      this->parent_->set_battery_voltage_high_override(value);
      break;
    case BATTERY_VOLTAGE_LOW:
      this->parent_->set_battery_voltage_low_override(value);
      break;
  }

  this->pref_.save(&value);

  ESP_LOGI(TAG_NUMBER, "Set %s calibration to %.2f V", this->calibration_type_to_string(), value);
  this->publish_state(value);
}

const char *UpsCalibrationNumber::calibration_type_to_string() const {
  switch (this->calibration_type_) {
    case BATTERY_VOLTAGE_HIGH:
      return "battery_voltage_high";
    case BATTERY_VOLTAGE_LOW:
      return "battery_voltage_low";
    default:
      return "unknown";
  }
}

}  // namespace ups_hid
}  // namespace esphome