#pragma once

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "ups_hid.h"

namespace esphome
{
  namespace ups_hid
  {

    class UpsHidSensor : public sensor::Sensor, public Component
    {
    public:
      void set_sensor_type(const std::string &type) { sensor_type_ = type; }
      void dump_config() override;

    protected:
      std::string sensor_type_;
    };

  } // namespace ups_hid
} // namespace esphome