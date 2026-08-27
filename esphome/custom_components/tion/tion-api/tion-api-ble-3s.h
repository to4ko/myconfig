#pragma once

#include "tion-api-protocol.h"

namespace dentra {
namespace tion {

class Tion3sBleProtocol : public TionProtocol<tion_any_frame_t> {
 public:
  bool read_data(const uint8_t *data, size_t size);

  bool write_frame(uint16_t type, const void *data, size_t size);

  const char *get_ble_service() const;
  const char *get_ble_char_tx() const;
  const char *get_ble_char_rx() const;
};

}  // namespace tion
}  // namespace dentra
