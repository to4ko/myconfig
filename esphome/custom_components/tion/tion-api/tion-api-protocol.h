#pragma once

#include <cinttypes>
#include <etl/delegate.h>

namespace dentra {
namespace tion {

// NOLINTNEXTLINE(readability-identifier-naming)
template<class data_type> struct tion_frame_t {
  uint16_t type;
  data_type data;
  constexpr static size_t head_size() { return sizeof(type); }
} __attribute__((__packed__));
using tion_any_frame_t = tion_frame_t<uint8_t[0]>;

// NOLINTNEXTLINE(readability-identifier-naming)
template<class data_type> struct tion_ble_frame_t {
  uint16_t type;
  uint32_t ble_request_id;  // always 1
  data_type data;
  constexpr static size_t head_size() { return sizeof(type) + sizeof(ble_request_id); }
} __attribute__((__packed__));

using tion_any_ble_frame_t = tion_ble_frame_t<uint8_t[0]>;

template<class frame_spec_t> class TionProtocol {
 public:
  using frame_spec_type = frame_spec_t;

  using reader_type = etl::delegate<void(const frame_spec_t &data, size_t size)>;
  // TODO move to protected
  reader_type reader{};
  void set_reader(reader_type &&reader) { this->reader = reader; }

  using writer_type = etl::delegate<bool(const uint8_t *data, size_t size)>;
  // TODO move to protected
  writer_type writer{};
  void set_writer(writer_type &&writer) { this->writer = writer; }
};

}  // namespace tion
}  // namespace dentra
