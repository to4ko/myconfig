#pragma once

#include <cstring>  // std::memset

#include "tion-api-protocol.h"

namespace dentra {
namespace tion {

class TionUartReader {
 public:
  virtual int available() = 0;
  virtual bool read_array(void *data, size_t size) = 0;
};

template<size_t frame_max_size_value> class TionUartProtocolBase : public TionProtocol<tion_any_frame_t> {
 protected:
  enum { FRAME_MAX_SIZE = frame_max_size_value };
  // NOLINTNEXTLINE(readability-identifier-naming)
  enum read_frame_result_t {
    // let perform read next frame on next loop
    READ_NEXT_LOOP = 0,
    // stay read frame in current loop
    READ_THIS_LOOP = 1,
  };
  uint8_t buf_[FRAME_MAX_SIZE]{};
  void reset_buf_() { std::memset(this->buf_, 0, sizeof(this->buf_)); }
};

}  // namespace tion
}  // namespace dentra
