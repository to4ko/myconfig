#include "sensor_numeric.h"
#include "esphome/core/log.h"

namespace esphome
{
  namespace ups_hid
  {

    static const char *const S_TAG = "ups_hid.sensor";

    void UpsHidSensor::dump_config()
    {
      ESP_LOGCONFIG(S_TAG, "UPS HID Sensor:");
      ESP_LOGCONFIG(S_TAG, "  Type: %s", sensor_type_.c_str());
      LOG_SENSOR("  ", "Sensor", this);
    }

  } // namespace ups_hid
} // namespace esphome