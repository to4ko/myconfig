#include "sensor_text.h"
#include "esphome/core/log.h"

namespace esphome
{
  namespace ups_hid
  {

    static const char *const TXT_TAG = "ups_hid.text_sensor";

    void UpsHidTextSensor::dump_config()
    {
      ESP_LOGCONFIG(TXT_TAG, "UPS HID Text Sensor:");
      ESP_LOGCONFIG(TXT_TAG, "  Type: %s", sensor_type_.c_str());
      LOG_TEXT_SENSOR("  ", "Text Sensor", this);
    }

  } // namespace ups_hid
} // namespace esphome