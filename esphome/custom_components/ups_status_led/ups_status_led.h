#pragma once

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/components/time/real_time_clock.h"
#include "../ups_hid/ups_hid.h"

// Light component include
#include "esphome/components/light/light_state.h"

// Thread safety
#include <mutex>

#ifdef USE_SWITCH
#include "esphome/components/switch/switch.h"
#endif

#ifdef USE_NUMBER
#include "esphome/components/number/number.h"
#endif

#ifdef USE_TEXT_SENSOR
#include "esphome/components/text_sensor/text_sensor.h"
#endif

namespace esphome {
namespace ups_status_led {

// LED patterns (solid colors for simple indication)
enum class LedPattern : uint8_t {
  OFF = 0,
  CRITICAL_SOLID,       // Solid red - emergencies
  BATTERY_WARNING,      // Solid orange - on battery
  CHARGING_SOLID,       // Solid yellow - charging
  NORMAL_SOLID,         // Solid green - normal (or gradient)
  OFFLINE_SOLID,        // Solid blue - UPS disconnected
  NO_DATA_SOLID,        // Solid purple - no data from UPS component
  COMPONENT_ERROR       // Solid white - component error
};

// Battery color mode configuration
enum class BatteryColorMode : uint8_t {
  DISCRETE,     // Green > 50%, Orange 20-50%, Red < 20%
  GRADIENT      // Smooth green→yellow→red transition
};

/**
 * @brief SOLID-inspired UPS Status LED Component
 * 
 * Simplified version that maintains separation of concerns while being ESPHome compatible.
 * Follows Single Responsibility and Open/Closed principles where possible.
 */
class UpsStatusLedComponent : public Component {
 public:
  float get_setup_priority() const override { return setup_priority::HARDWARE - 1.0f; }
  void setup() override;
  void loop() override;
  void dump_config() override;
  
  // Configuration setters
  void set_ups_hid(ups_hid::UpsHidComponent *ups) { ups_hid_ = ups; }
  void set_light(light::LightState *light) { light_ = light; }
  void set_time(time::RealTimeClock *time) { time_ = time; }
  
  // Basic settings
  void set_enabled(bool enabled) { enabled_ = enabled; }
  void set_brightness(float brightness) { brightness_ = brightness; }
  void set_battery_color_mode(BatteryColorMode mode) { battery_color_mode_ = mode; }
  
  // Night mode configuration (for YAML config)
  void set_night_mode_enabled(bool enabled) { night_mode_enabled_ = enabled; }
  void set_night_mode_brightness(float brightness) { night_mode_brightness_ = brightness; }
  void set_night_mode_start_time(uint8_t hour, uint8_t minute) {
    night_mode_start_hour_ = hour;
    night_mode_start_minute_ = minute;
  }
  void set_night_mode_end_time(uint8_t hour, uint8_t minute) {
    night_mode_end_hour_ = hour;
    night_mode_end_minute_ = minute;
  }
  
  // Battery thresholds
  void set_battery_low_threshold(float threshold) { battery_low_threshold_ = threshold; }
  void set_battery_warning_threshold(float threshold) { battery_warning_threshold_ = threshold; }
  
  // Home Assistant API methods (for web controls)
  void set_enabled_api(bool enabled) { 
    std::lock_guard<std::mutex> lock(state_mutex_);
    enabled_ = enabled; 
    if (!enabled_) {
      set_led_color(0, 0, 0, 0);  // Turn off immediately when disabled
    } else {
      force_update_ = true;  // Flag for next loop update
    }
  }
  void set_brightness_api(float brightness) { 
    std::lock_guard<std::mutex> lock(state_mutex_);
    brightness_ = brightness; 
    force_update_ = true;  // Flag for next loop update
  }
  void set_night_mode_enabled_api(bool enabled) { 
    std::lock_guard<std::mutex> lock(state_mutex_);
    night_mode_enabled_ = enabled; 
    force_update_ = true;  // Flag for next loop update
  }
  void set_battery_color_mode_api(BatteryColorMode mode) { 
    std::lock_guard<std::mutex> lock(state_mutex_);
    battery_color_mode_ = mode; 
    force_update_ = true;  // Flag for next loop update
  }
  
  // Night mode API methods (for web UI runtime control)
  void set_night_mode_brightness_api(float brightness) { 
    std::lock_guard<std::mutex> lock(state_mutex_);
    night_mode_brightness_ = brightness; 
    force_update_ = true;  // Flag for next loop update
  }
  void set_night_mode_start_time_api(uint8_t hour, uint8_t minute) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    night_mode_start_hour_ = hour;
    night_mode_start_minute_ = minute;
    force_update_ = true;  // Flag for next loop update
  }
  void set_night_mode_end_time_api(uint8_t hour, uint8_t minute) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    night_mode_end_hour_ = hour;
    night_mode_end_minute_ = minute;
    force_update_ = true;  // Flag for next loop update
  }
  
  // Status getters
  bool is_enabled() const { return enabled_; }
  float get_brightness() const { return brightness_; }
  bool is_night_mode_active() const { return is_night_time(); }
  LedPattern get_current_pattern() const { return current_pattern_; }
  
  // Home Assistant entity setters
#ifdef USE_SWITCH
  void set_enabled_switch(switch_::Switch *sw) { enabled_switch_ = sw; }
  void set_night_mode_switch(switch_::Switch *sw) { night_mode_switch_ = sw; }
#endif
#ifdef USE_NUMBER
  void set_brightness_number(number::Number *num) { brightness_number_ = num; }
#endif
#ifdef USE_TEXT_SENSOR
  void set_status_text_sensor(text_sensor::TextSensor *sensor) { status_text_sensor_ = sensor; }
#endif

 protected:
  // SOLID principle: Single Responsibility - each method has one focused task
  LedPattern evaluate_pattern();
  void apply_pattern(LedPattern pattern);
  void calculate_color(float &r, float &g, float &b, LedPattern pattern, float brightness);
  float calculate_brightness();
  bool is_night_time() const;
  
  // Pattern implementation - simplified solid colors only
  
  // Hardware abstraction
  void set_led_color(float r, float g, float b, float brightness);
  void initialize_light_component();
  
 private:
  // Dependencies (Dependency Inversion principle)
  ups_hid::UpsHidComponent *ups_hid_{nullptr};
  light::LightState *light_{nullptr};
  time::RealTimeClock *time_{nullptr};
  
  // Configuration
  bool enabled_{true};
  float brightness_{0.8f};
  BatteryColorMode battery_color_mode_{BatteryColorMode::DISCRETE};
  
  // Night mode settings
  bool night_mode_enabled_{true};
  float night_mode_brightness_{0.3f};  // 30% of day brightness, ensures min 20% when base is 80%
  uint8_t night_mode_start_hour_{22};
  uint8_t night_mode_start_minute_{0};
  uint8_t night_mode_end_hour_{7};
  uint8_t night_mode_end_minute_{0};
  
  // Battery thresholds
  float battery_low_threshold_{20.0f};
  float battery_warning_threshold_{50.0f};
  
  // Pattern state tracking
  LedPattern current_pattern_{LedPattern::OFF};
  uint32_t pattern_start_time_{0};
  uint32_t last_update_{0};
  bool force_update_{false};  // Flag for immediate updates from API calls
  static constexpr uint32_t UPDATE_INTERVAL_MS = 50;   // 20Hz update rate for faster response
  
  // Hardware brightness constraints
  static constexpr float MIN_HARDWARE_BRIGHTNESS = 0.2f;  // 20% minimum for switch meaning
  
  // Home Assistant entities
#ifdef USE_SWITCH
  switch_::Switch *enabled_switch_{nullptr};
  switch_::Switch *night_mode_switch_{nullptr};
#endif
#ifdef USE_NUMBER
  number::Number *brightness_number_{nullptr};
#endif
#ifdef USE_TEXT_SENSOR
  text_sensor::TextSensor *status_text_sensor_{nullptr};
#endif

  // Thread safety mutex
  mutable std::mutex state_mutex_;
};

}  // namespace ups_status_led
}  // namespace esphome