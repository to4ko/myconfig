#pragma once

#include <cstdint>
#include <string>

#ifdef TION_ESPHOME
#include "esphome/core/helpers.h"
#include "esphome/core/hal.h"
#include "esphome/core/optional.h"
#endif

namespace dentra {
namespace tion {

#ifdef TION_ESPHOME
inline std::string tion_hexencode(const void *data, uint32_t size) {
  return esphome::format_hex_pretty(static_cast<const uint8_t *>(data), size);
}
inline void yield() { esphome::yield(); }
inline uint32_t millis() { return esphome::millis(); }
using esphome::optional;
using esphome::str_sprintf;
#else
#define PACKED __attribute__((packed))
std::string tion_hexencode(const void *data, uint32_t size);
inline void yield() {}
#include <optional>
using std::optional;
std::string __attribute__((format(printf, 1, 2))) str_sprintf(const char *fmt, ...);
#endif

#if !__has_builtin(__builtin_bswap16)
#include <byteswap.h>
#define __builtin_bswap16 __bswap_16
#endif

#define hex_cstr(data, size) tion_hexencode(data, size).c_str()

const char *get_flag_bits(uint8_t flags);

}  // namespace tion
}  // namespace dentra
