#pragma once

#include "esphome/core/helpers.h"
#include "esphome/core/string_ref.h"

namespace esphome {
namespace tion {

inline uint8_t fan_mode_to_speed(const char *fan_mode) { return *fan_mode - '0'; }
inline uint8_t fan_mode_to_speed(const std::string &fan_mode) { return fan_mode_to_speed(fan_mode.c_str()); }
inline uint8_t fan_mode_to_speed(const optional<std::string> &fan_mode) {
  return fan_mode.has_value() ? fan_mode_to_speed(fan_mode.value()) : 0;
}
// climate::Climate::get_custom_fan_mode() (ESPHome >= 2026.x) возвращает
// StringRef, а не optional<std::string>; пустой (не заданный) режим
// представлен пустой строкой, а не отсутствием значения, поэтому обрабатываем
// это явно, а не полагаемся на *fan_mode - '0' на пустой строке.
inline uint8_t fan_mode_to_speed(const StringRef &fan_mode) {
  return fan_mode.empty() ? 0 : fan_mode_to_speed(fan_mode.c_str());
}

inline std::string fan_speed_to_mode(uint8_t fan_speed) {
  char fan_mode[2] = {static_cast<char>(fan_speed + '0'), 0};
  return std::string(fan_mode);
}

}  // namespace tion
}  // namespace esphome
