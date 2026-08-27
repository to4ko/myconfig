#include <cstdlib>
#include <string>
#include <climits>  // CHAR_BIT

#include "utils.h"

namespace dentra {
namespace tion {

#ifndef TION_ESPHOME

static inline std::string hex(const void *data, uint32_t size, char sep, bool add_size) {
  static const char hexmap[] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'};
  const uint8_t *data_ptr = static_cast<const uint8_t *>(data);
  std::string str;

  if (size > 0) {
    int mul = 2;
    if (sep != 0) {
      str.resize(size * (++mul) - 1);
    } else {
      str.resize(size * mul);
    }
    for (int i = 0; i < size; ++i) {
      str[mul * i + 0] = hexmap[(*data_ptr & 0xF0) >> 4];
      str[mul * i + 1] = hexmap[(*data_ptr & 0x0F) >> 0];
      if (sep != 0 && i < size - 1) {
        str[mul * i + 2] = sep;
      }
      data_ptr++;
    }
    str += ' ';
  }

  if (add_size) {
    str += '(';
    str += std::to_string(size);
    str += ')';
  }
  return str;
}

std::string tion_hexencode(const void *data, uint32_t size) { return hex(data, size, '.', true); };

#endif

const char *get_flag_bits(uint8_t flags) {
  static char flags_bits[CHAR_BIT + 1]{};
  for (int i = 0; i < CHAR_BIT; i++) {
    flags_bits[(CHAR_BIT - 1) - i] = ((flags >> i) & 1) + '0';
  }
  return flags_bits;
}

}  // namespace tion
}  // namespace dentra
