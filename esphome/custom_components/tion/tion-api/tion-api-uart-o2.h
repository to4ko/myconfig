#pragma once

#include "tion-api-o2.h"
#include "tion-api-uart.h"

namespace dentra {
namespace tion_o2 {

// 20 = sizeof(tiono2_frame_t)+type+crc+1
class TionO2UartProtocol : public tion::TionUartProtocolBase<32> {
 public:
  TionO2UartProtocol(const TionO2UartProtocol &) = delete;             // non construction-copyable
  TionO2UartProtocol &operator=(const TionO2UartProtocol &) = delete;  // non copyable

  explicit TionO2UartProtocol(bool is_proxy = false);

  void read_uart_data(tion::TionUartReader *io);

  bool write_frame(uint16_t type, const void *data, size_t size);

 protected:
  size_t (*get_frame_size)(uint8_t);

  uint8_t crc(uint8_t init, const void *data, size_t size) const;
  uint8_t crc(const void *data, size_t size) const { return this->crc(0xFF, data, size); }

  size_t frame_size_{};

  /// Reads a frame starting with size for hw uart or continue reading for sw uart
  int read_frame_(tion::TionUartReader *io);
  void skip_uart_data_(tion::TionUartReader *io);
};

}  // namespace tion_o2
}  // namespace dentra
