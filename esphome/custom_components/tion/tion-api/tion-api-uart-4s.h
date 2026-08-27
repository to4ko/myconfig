#pragma once

#include "tion-api-uart.h"

namespace dentra {
namespace tion {

class Tion4sUartProtocol : public TionUartProtocolBase<0x2A> {
 public:
  void read_uart_data(TionUartReader *io);

  bool write_frame(uint16_t type, const void *data, size_t size);

 protected:
  /// Reads a frame starting with size for hw uart or continue reading for sw uart
  read_frame_result_t read_frame_(TionUartReader *io);
};

}  // namespace tion
}  // namespace dentra
