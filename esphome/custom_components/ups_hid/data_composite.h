#pragma once

#include "data_battery.h"
#include "data_power.h"
#include "data_device.h"
#include "data_test.h"
#include "data_config.h"
#include <cstdint>
#include <cstring>  // For memcmp

namespace esphome {
namespace ups_hid {

/**
 * Clean UPS Composite Data Structure
 * 
 * Contains all UPS data organized into logical components following
 * Single Responsibility Principle. No legacy compatibility code.
 */
struct UpsCompositeData {
  // Specialized data components
  BatteryData battery;
  PowerData power;
  DeviceInfo device;
  TestStatus test;
  ConfigData config;
  
  // Validation and utility methods
  bool is_valid() const {
    return battery.is_valid() || power.is_valid() || device.is_valid() || 
           test.is_valid() || config.is_valid();
  }
  
  bool has_core_data() const {
    return battery.is_valid() && power.is_valid();
  }
  
  // Clean reset without legacy flags
  void reset() {
    battery.reset();
    power.reset();
    device.reset();
    test.reset();
    config.reset();
  }
  
  // Copy constructor and assignment for safe copying
  UpsCompositeData() = default;
  UpsCompositeData(const UpsCompositeData&) = default;
  UpsCompositeData& operator=(const UpsCompositeData&) = default;
  UpsCompositeData(UpsCompositeData&&) = default;
  UpsCompositeData& operator=(UpsCompositeData&&) = default;
};

// Type alias for cleaner naming
using UpsData = UpsCompositeData;

}  // namespace ups_hid
}  // namespace esphome