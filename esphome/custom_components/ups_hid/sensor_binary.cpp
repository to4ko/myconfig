#include "sensor_binary.h"
#include "esphome/core/log.h"

namespace esphome {
namespace ups_hid {

static const char *const TAG_BINARY = "ups_hid.binary_sensor";

void UpsHidBinarySensor::dump_config() {
  ESP_LOGCONFIG(TAG_BINARY, "UPS HID Binary Sensor:");
  ESP_LOGCONFIG(TAG_BINARY, "  Type: %s", sensor_type_.c_str());
  LOG_BINARY_SENSOR("  ", "Binary Sensor", this);
}

}  // namespace ups_hid
}  // namespace esphome