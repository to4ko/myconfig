#pragma once

#include "esphome.h"

class XiaomiLight : public Component, public LightOutput {
 public:
  XiaomiLight(FloatOutput *cw_white_color, FloatOutput *brightness)
    {
        cw_white_color_ = cw_white_color;
        brightness_ = brightness;
        cold_white_temperature_ = 175;
        warm_white_temperature_ = 333;
        constant_brightness_ = true;
    }
  LightTraits get_traits() override {
    auto traits = light::LightTraits();
    traits.set_supports_brightness(true);
    traits.set_supports_rgb(false);
    traits.set_supports_rgb_white_value(false);
    traits.set_supports_color_temperature(true);
    traits.set_min_mireds(this->cold_white_temperature_);
    traits.set_max_mireds(this->warm_white_temperature_);
    return traits;
  }

  void write_state(LightState *state) override {
    float brightness, cwhite, wwhite;
    state->current_values_as_cwww(&cwhite, &wwhite, this->constant_brightness_);
//    ESP_LOGD("custom", "The value cwhite: %f", cwhite);
//    ESP_LOGD("custom", "The value wwhite: %f", wwhite);
    state->current_values_as_brightness(&brightness);
//    ESP_LOGD("custom", "The value brightness: %f", brightness);
    this->cw_white_color_->set_level(cwhite+(1-brightness));
    this->brightness_->set_level(brightness);
  }
  protected:
    FloatOutput *cw_white_color_;
    FloatOutput *brightness_;
    float cold_white_temperature_;
    float warm_white_temperature_;
    bool constant_brightness_;
};
