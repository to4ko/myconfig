#pragma once

// Заводские поправки Sonoff S60 поверх измерений CSE7759B/CSE7766.
// Формулы и определение платы: adamsthws/Sonoff-OTA, ESPHome/sonoff_s60.yaml.
// Сначала читаем NVS розетки; резерв передаётся из её собственного дампа.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <string>
#include <vector>

#include <driver/gpio.h>
#include <esp_rom_sys.h>
#include <nvs.h>
#include <soc/soc.h>
#include <soc/usb_serial_jtag_reg.h>

#include "esphome/core/log.h"

namespace sonoff_s60 {

class Calibration {
 public:
  void setup(const std::array<double, 18> &backup) {
    coefficients_ = backup;
    const char *source = "from backup";

    // GPIO19 занят USB-JTAG, пока не отключены USB-площадки.
    CLEAR_PERI_REG_MASK(USB_SERIAL_JTAG_CONF0_REG, USB_SERIAL_JTAG_USB_PAD_ENABLE);
    const gpio_num_t pins[] = {GPIO_NUM_6, GPIO_NUM_10, GPIO_NUM_19};
    for (auto pin : pins) {
      gpio_reset_pin(pin);
      gpio_set_direction(pin, GPIO_MODE_INPUT);
      gpio_set_pull_mode(pin, GPIO_PULLUP_ONLY);
    }
    esp_rom_delay_us(100);
    bool all_high = true;
    for (auto pin : pins) {
      if (gpio_get_level(pin) == 0) all_high = false;
    }
    meter_factor_ = all_high ? 1.0f : 1.02f;

    std::string content;
    nvs_handle_t handle;
    if (nvs_open("user_unusual", NVS_READONLY, &handle) == ESP_OK) {
      size_t length = 0;
      if (nvs_get_blob(handle, "content", nullptr, &length) == ESP_OK &&
          length > 0 && length <= 65536) {
        content.resize(length);
        if (nvs_get_blob(handle, "content", &content[0], &length) != ESP_OK) content.clear();
      }
      nvs_close(handle);
    }

    std::array<double, 18> stock;
    if (parse_stock_(content, stock)) {
      coefficients_ = stock;
      source = "stock NVS";
    }
    status_ = std::string(source) + ", factor " + (all_high ? "1.00" : "1.02");
    ESP_LOGI("s60_calibration", "Calibration: %s", status_.c_str());
  }

  float current(float value) const { return apply_(value, raw_power_ < 300.0f ? 0 : 9); }

  float voltage(float value) const {
    return apply_(value * meter_factor_, (raw_power_ < 300.0f ? 0 : 9) + 3);
  }

  float power(float value) {
    raw_power_ = value * meter_factor_;
    const float corrected = apply_(raw_power_, (raw_power_ < 300.0f ? 0 : 9) + 6);
    return corrected < 0.0f ? 0.0f : corrected;
  }

  const std::string &status() const { return status_; }

 private:
  // В NVS записаны две единицы и 18 коэффициентов: два диапазона по 9 чисел.
  static bool parse_stock_(const std::string &content, std::array<double, 18> &out) {
    size_t start = content.find("\"calib_coefficient0\"");
    if (start == std::string::npos) return false;
    start = content.find(':', start);
    if (start == std::string::npos) return false;
    start = content.find('"', start + 1);
    if (start == std::string::npos) return false;
    const size_t end = content.find('"', start + 1);
    if (end == std::string::npos) return false;
    const std::string text = content.substr(start + 1, end - start - 1);
    const char *at = text.c_str();
    std::vector<double> numbers;
    while (*at != '\0') {
      if (*at == ',' || *at == '[' || *at == ']' || *at == ' ' || *at == '\t') {
        ++at;
        continue;
      }
      char *next;
      const double value = strtod(at, &next);
      if (next == at || !std::isfinite(value) || numbers.size() >= 20) return false;
      numbers.push_back(value);
      at = next;
    }
    if (numbers.size() != 20 || numbers[0] != 1.0 || numbers[1] != 1.0) return false;
    std::copy_n(numbers.begin() + 2, 18, out.begin());
    return true;
  }

  // Пересчёт заводской формулы из мА/мВ/мВт в А/В/Вт.
  float apply_(float value, size_t offset) const {
    const auto &c = coefficients_;
    return c[offset] * 1e-4 * value * value + c[offset + 1] / 1e6 * value + c[offset + 2] / 1e9;
  }

  std::array<double, 18> coefficients_{};
  float raw_power_{0.0f};
  float meter_factor_{1.0f};
  std::string status_{"unknown"};
};

inline Calibration calibration;

}  // namespace sonoff_s60
