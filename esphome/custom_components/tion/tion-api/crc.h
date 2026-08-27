#pragma once

#include <cstdint>
#include <cstddef>

namespace dentra {
namespace tion {

/// CRC-16/CCITT-FALSE. The result is in big-endian byte order.
uint16_t crc16_ccitt_false(uint16_t init, const void *data, size_t size);

/// CRC-16/CCITT-FALSE with 0xFFFF initial value. The result is in big-endian byte order.
inline uint16_t crc16_ccitt_false_ffff(const void *data, size_t size) { return crc16_ccitt_false(0xFFFF, data, size); }

}  // namespace tion
}  // namespace dentra
