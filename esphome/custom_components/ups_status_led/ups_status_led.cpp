#include "ups_status_led.h"
#include "esphome/core/log.h"
#include <algorithm>

namespace esphome {
namespace ups_status_led {

static const char *const TAG = "ups_status_led";

void UpsStatusLedComponent::setup() {
  ESP_LOGI(TAG, "*** UPS STATUS LED SETUP STARTING ***");
  ESP_LOGCONFIG(TAG, "Setting up UPS Status LED...");
  
  // Validate required components
  if (!ups_hid_) {
    ESP_LOGE(TAG, "UPS HID component is required!");
    mark_failed();
    return;
  }
  ESP_LOGI(TAG, "UPS HID component found and linked");

  if (!light_) {
    ESP_LOGE(TAG, "Light component is required!");
    mark_failed();
    return;
  }
  ESP_LOGI(TAG, "Light component found and linked");
  
  // Initialize light to known OFF state during setup
  // This ensures the light component is working and ready
  initialize_light_component();
  
  // Initialize Home Assistant entities with SAFE callbacks
#ifdef USE_SWITCH
  if (enabled_switch_) {
    enabled_switch_->add_on_state_callback([this](bool state) {
      // SAFE: Use flag-based approach, never direct calls during setup
      std::lock_guard<std::mutex> lock(state_mutex_);
      enabled_ = state;
      force_update_ = true;  // Let loop handle the update
      ESP_LOGD(TAG, "Enabled switch changed to: %s", state ? "ON" : "OFF");
    });
  }
  if (night_mode_switch_) {
    night_mode_switch_->add_on_state_callback([this](bool state) {
      set_night_mode_enabled_api(state);
    });
  }
#endif
#ifdef USE_NUMBER
  if (brightness_number_) {
    brightness_number_->add_on_state_callback([this](float value) {
      set_brightness_api(value / 100.0f);  // Convert percentage to 0-1
    });
  }
#endif
  
  ESP_LOGI(TAG, "*** UPS STATUS LED SETUP COMPLETE ***");
  ESP_LOGCONFIG(TAG, "UPS Status LED setup complete");
}

void UpsStatusLedComponent::loop() {
  static bool first_evaluation = true;
  static uint32_t startup_delay = 0;
  
  if (first_evaluation) {
    ESP_LOGI(TAG, "*** UPS STATUS LED FIRST LOOP - COMPONENT IS RUNNING ***");
    startup_delay = millis() + 2000;  // 2 second startup delay for UPS initialization
    first_evaluation = false;
  }
  
  uint32_t now = millis();
  
  // Thread-safe state access
  std::lock_guard<std::mutex> lock(state_mutex_);
  
  // Handle disabled state properly (don't interfere with startup delay)
  if (!enabled_) {
    // Only turn off LED if we're past startup or if we've already started
    if (startup_delay == 0 || now >= startup_delay) {
      ESP_LOGD(TAG, "LED disabled - turning off");
      set_led_color(0, 0, 0, 0);
      startup_delay = 0;  // Clear startup delay
      force_update_ = false;  // Clear flag
    }
    return;
  }
  
  // Wait for startup delay to complete
  if (startup_delay > 0 && now < startup_delay) {
    return;
  }
  
  // Clear startup delay after waiting
  bool startup_complete = false;
  if (startup_delay > 0) {
    startup_complete = true;
    startup_delay = 0;
    force_update_ = true;  // Force first update after startup delay
    ESP_LOGI(TAG, "LED startup delay complete - forcing initial pattern evaluation");
  }
  
  bool should_update = (now - last_update_ >= UPDATE_INTERVAL_MS) || force_update_;
  
  if (should_update) {
    // Evaluate and apply pattern
    LedPattern new_pattern = evaluate_pattern();
    
    // Update on startup completion, pattern changes, or forced updates
    if (startup_complete || new_pattern != current_pattern_ || force_update_) {
      ESP_LOGD(TAG, "Pattern update: reason=%s, pattern=%d, forced=%s", 
               startup_complete ? "STARTUP_COMPLETE" : (new_pattern != current_pattern_ ? "PATTERN_CHANGE" : "FORCED"),
               (int)new_pattern,
               force_update_ ? "true" : "false");
      
      current_pattern_ = new_pattern;
      pattern_start_time_ = now;
      apply_pattern(current_pattern_);
      force_update_ = false;  // Clear flag after update
    }
    last_update_ = now;
  }
  
  // Update Home Assistant entities periodically
  static uint32_t last_ha_update = 0;
  if (now - last_ha_update > 1000) {  // Update every second
#ifdef USE_TEXT_SENSOR
    if (status_text_sensor_) {
      std::string pattern_name;
      switch (current_pattern_) {
        case LedPattern::NORMAL_SOLID: pattern_name = "Normal"; break;
        case LedPattern::CHARGING_SOLID: pattern_name = "Charging"; break;
        case LedPattern::BATTERY_WARNING: pattern_name = "Battery Warning"; break;
        case LedPattern::CRITICAL_SOLID: pattern_name = "Critical"; break;
        case LedPattern::OFFLINE_SOLID: pattern_name = "Offline"; break;
        case LedPattern::NO_DATA_SOLID: pattern_name = "No Data"; break;
        case LedPattern::COMPONENT_ERROR: pattern_name = "Component Error"; break;
        default: pattern_name = "Off"; break;
      }
      if (status_text_sensor_->state != pattern_name) {
        status_text_sensor_->publish_state(pattern_name);
      }
    }
#endif
    last_ha_update = now;
  }
}

void UpsStatusLedComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "UPS Status LED:");
  ESP_LOGCONFIG(TAG, "  Enabled: %s", enabled_ ? "YES" : "NO");
  ESP_LOGCONFIG(TAG, "  Brightness: %.1f%%", brightness_ * 100);
  ESP_LOGCONFIG(TAG, "  Battery Color Mode: %s", 
    battery_color_mode_ == BatteryColorMode::DISCRETE ? "Discrete" : "Gradient");
  ESP_LOGCONFIG(TAG, "  Night Mode: %s", night_mode_enabled_ ? "YES" : "NO");
  if (night_mode_enabled_) {
    ESP_LOGCONFIG(TAG, "    Time: %02d:%02d - %02d:%02d", 
      night_mode_start_hour_, night_mode_start_minute_,
      night_mode_end_hour_, night_mode_end_minute_);
    ESP_LOGCONFIG(TAG, "    Brightness: %.1f%%", night_mode_brightness_ * 100);
  }
  ESP_LOGCONFIG(TAG, "  Battery Thresholds:");
  ESP_LOGCONFIG(TAG, "    Low: %.1f%%", battery_low_threshold_);
  ESP_LOGCONFIG(TAG, "    Warning: %.1f%%", battery_warning_threshold_);
}

// SOLID principle: Single Responsibility - focused pattern evaluation
LedPattern UpsStatusLedComponent::evaluate_pattern() {
  if (!ups_hid_) {
    return LedPattern::COMPONENT_ERROR;
  }
  
  // Priority-based evaluation (highest priority first)
  if (!ups_hid_->is_connected()) {
    return LedPattern::OFFLINE_SOLID;
  }
  
  if (ups_hid_->is_low_battery() || ups_hid_->has_fault() || ups_hid_->is_overloaded()) {
    return LedPattern::CRITICAL_SOLID;
  }
  
  if (ups_hid_->is_on_battery()) {
    return LedPattern::BATTERY_WARNING;
  }
  
  if (ups_hid_->is_charging()) {
    return LedPattern::CHARGING_SOLID;
  }
  
  if (ups_hid_->is_online()) {
    return LedPattern::NORMAL_SOLID;
  }
  
  return LedPattern::NO_DATA_SOLID;
}

void UpsStatusLedComponent::apply_pattern(LedPattern pattern) {
  float brightness = calculate_brightness(); // Calculate once
  float r, g, b;
  calculate_color(r, g, b, pattern, brightness); // Pass brightness as parameter
  
  // Simple solid color display - no animations
  switch (pattern) {
    case LedPattern::CRITICAL_SOLID:
      // Critical: Solid red
      set_led_color(r, g, b, brightness);
      break;
    case LedPattern::BATTERY_WARNING:
      // Battery warning: Solid orange
      set_led_color(r, g, b, brightness);
      break;
    case LedPattern::CHARGING_SOLID:
      // Charging: Solid yellow
      set_led_color(r, g, b, brightness);
      break;
    case LedPattern::NORMAL_SOLID:
      // Normal: Solid green
      set_led_color(r, g, b, brightness);
      break;
    case LedPattern::OFFLINE_SOLID:
      // Offline: Solid blue
      set_led_color(r, g, b, brightness);
      break;
    case LedPattern::NO_DATA_SOLID:
      // No data: Solid purple
      set_led_color(r, g, b, brightness);
      break;
    case LedPattern::COMPONENT_ERROR:
      // Error: Solid white
      set_led_color(r, g, b, brightness);
      break;
    default:
      // Off
      set_led_color(0, 0, 0, 0);
      break;
  }
  
  ESP_LOGD(TAG, "Applying solid pattern: R=%.2f G=%.2f B=%.2f calculated_brightness=%.2f", r, g, b, brightness);
}

// SOLID principle: Single Responsibility - focused color calculation
void UpsStatusLedComponent::calculate_color(float &r, float &g, float &b, LedPattern pattern, float brightness) {
  // Check if night mode is active for color compensation
  bool night_active = night_mode_enabled_ && is_night_time();
  
  // Default colors for patterns with night mode color compensation
  switch (pattern) {
    case LedPattern::CRITICAL_SOLID:
      r = 1.0f; g = 0.0f; b = 0.0f; // Red
      break;
    case LedPattern::BATTERY_WARNING:
      // Orange: Boost green channel in night mode to maintain orange appearance
      r = 1.0f;
      if (night_active) {
        // Scale green boost based on how dim it is
        float boost_factor = 1.4f - brightness; // More boost when dimmer
        g = std::min(0.8f, 0.5f + boost_factor);
      } else {
        g = 0.5f;  // Normal orange
      }
      b = 0.0f;
      break;
    case LedPattern::CHARGING_SOLID:
      // Yellow: Boost green channel in night mode to prevent red appearance
      r = 1.0f;
      if (night_active) {
        // Scale green boost based on how dim it is
        float boost_factor = 1.5f - brightness; // More boost when dimmer
        g = std::min(1.3f, 1.0f + boost_factor);
      } else {
        g = 1.0f;  // Normal yellow
      }
      b = 0.0f;
      break;
    case LedPattern::NORMAL_SOLID:
      // Normal operation should always be solid green
      r = 0.0f; g = 1.0f; b = 0.0f; // Green
      break;
    case LedPattern::OFFLINE_SOLID:
      r = 0.0f; g = 0.0f; b = 1.0f; // Blue
      break;
    case LedPattern::NO_DATA_SOLID:
      r = 0.8f; g = 0.0f; b = 1.0f; // Purple
      break;
    case LedPattern::COMPONENT_ERROR:
      r = 1.0f; g = 1.0f; b = 1.0f; // White
      break;
    default:
      r = 0.0f; g = 0.0f; b = 0.0f; // Off
      break;
  }
}

float UpsStatusLedComponent::calculate_brightness() {
  float base_brightness = brightness_;
  bool night_active = night_mode_enabled_ && is_night_time();
  
  ESP_LOGD(TAG, "Brightness calc: base=%.2f, night_mode=%s, is_night=%s", 
           base_brightness, night_mode_enabled_ ? "ON" : "OFF", night_active ? "YES" : "NO");
  
  // Apply night mode
  if (night_active) {
    base_brightness *= night_mode_brightness_;
    ESP_LOGD(TAG, "Night mode applied: %.2f * %.2f = %.2f", 
             brightness_, night_mode_brightness_, base_brightness);
  }
  
  // Enforce minimum hardware brightness to make enabled switch meaningful
  float final_brightness = std::max(base_brightness, MIN_HARDWARE_BRIGHTNESS);
  
  if (final_brightness != base_brightness) {
    ESP_LOGD(TAG, "Applied minimum brightness: %.2f → %.2f", base_brightness, final_brightness);
  }
  
  return final_brightness;
}

bool UpsStatusLedComponent::is_night_time() const {
  if (!time_ || !time_->now().is_valid()) {
    return false;
  }
  
  int current_hour = time_->now().hour;
  int current_minute = time_->now().minute;
  int current_time_minutes = current_hour * 60 + current_minute;
  int start_time_minutes = night_mode_start_hour_ * 60 + night_mode_start_minute_;
  int end_time_minutes = night_mode_end_hour_ * 60 + night_mode_end_minute_;
  
  if (start_time_minutes <= end_time_minutes) {
    return (current_time_minutes >= start_time_minutes && current_time_minutes < end_time_minutes);
  } else {
    return (current_time_minutes >= start_time_minutes || current_time_minutes < end_time_minutes);
  }
}


// Hardware abstraction
void UpsStatusLedComponent::set_led_color(float r, float g, float b, float brightness) {
  if (!light_) {
    ESP_LOGW(TAG, "Light component not available - cannot set LED color");
    return;
  }
  
  ESP_LOGD(TAG, "Setting LED: R=%.2f G=%.2f B=%.2f Brightness=%.2f", r, g, b, brightness);
  
  // Don't pre-multiply RGB by brightness - let light component handle it
  ESP_LOGD(TAG, "Sending to light: RGB=(%.2f,%.2f,%.2f) Brightness=%.2f", r, g, b, brightness);
  
  // Use light component API properly
  auto call = light_->make_call();
  call.set_state(true);
  call.set_rgb(r, g, b);           // Set color
  call.set_brightness(brightness); // Set brightness separately  
  call.perform();
}

void UpsStatusLedComponent::initialize_light_component() {
  if (!light_) {
    ESP_LOGE(TAG, "Cannot initialize light component - not available");
    return;
  }
  
  ESP_LOGI(TAG, "Initializing light component to known OFF state");
  
  // Set light to known OFF state and test that it works
  auto call = light_->make_call();
  call.set_state(false);  // Ensure light is OFF during setup
  call.perform();
  
  ESP_LOGI(TAG, "Light component initialized successfully");
}

}  // namespace ups_status_led
}  // namespace esphome