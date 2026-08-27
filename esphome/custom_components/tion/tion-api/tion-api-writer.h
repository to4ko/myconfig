#pragma once

#pragma once

#include <cinttypes>
#include <etl/delegate.h>

namespace dentra {
namespace tion {

class TionApiWriter {
 public:
  using writer_type = etl::delegate<bool(uint16_t type, const void *data, size_t size)>;
  void set_writer(writer_type &&writer) { this->writer_ = writer; }

  // Write any frame data.
  bool write_frame(uint16_t type, const void *data, size_t size) const;
  /// Write a frame with empty data.
  bool write_frame(uint16_t type) const { return this->write_frame(type, nullptr, 0); }
  /// Write a frame data struct.
  template<class T, std::enable_if_t<std::is_class_v<T>, bool> = true>
  bool write_frame(uint16_t type, const T &data) const {
    return this->write_frame(type, &data, sizeof(data));
  }

 protected:
  writer_type writer_{};
};

}  // namespace tion
}  // namespace dentra
