#pragma once

#include "tion-api-uart.h"

namespace dentra {
namespace tion {

// 20 = sizeof(tion3s_frame_t)
class Tion3sUartProtocol : public TionUartProtocolBase<20> {
 public:
  Tion3sUartProtocol(const Tion3sUartProtocol &) = delete;             // non construction-copyable
  Tion3sUartProtocol &operator=(const Tion3sUartProtocol &) = delete;  // non copyable

  Tion3sUartProtocol(uint8_t head_type = tion_3s::FRAME_MAGIC_RSP) : head_type_(head_type) {}

  void read_uart_data(TionUartReader *io);

  bool write_frame(uint16_t type, const void *data, size_t size);

 protected:
  const uint8_t head_type_;

  /// Reads a frame starting with size for hw uart or continue reading for sw uart
  read_frame_result_t read_frame_(TionUartReader *io);
};

}  // namespace tion
}  // namespace dentra
