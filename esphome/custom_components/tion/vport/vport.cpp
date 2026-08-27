#include "esphome/core/log.h"
#include "esphome/core/helpers.h"

#include "vport.h"

namespace esphome {
namespace vport {
static const char *const TAG = "vport";

void VPortBase::log_frame_(const void *data, size_t size) {
  ESP_LOGV(TAG, "VRX: %s", format_hex_pretty(reinterpret_cast<const uint8_t *>(data), size).c_str());
}

void VPortBase::log_write_(const void *data, size_t size) {
  ESP_LOGV(TAG, "VTX: %s", format_hex_pretty(reinterpret_cast<const uint8_t *>(data), size).c_str());
}

}  // namespace vport
}  // namespace esphome
