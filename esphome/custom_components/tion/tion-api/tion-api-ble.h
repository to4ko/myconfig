#pragma once

#include "tion-api.h"

namespace dentra {
namespace tion {

template<class ProtocolT> class TionBleProtocol : public ProtocolT {
 public:
  const char *get_ble_service() const { return ProtocolT::get_ble_service(); }
  const char *get_ble_char_tx() const { return ProtocolT::get_ble_char_tx(); }
  const char *get_ble_char_rx() const { return ProtocolT::get_ble_char_rx(); }
};

}  // namespace tion
}  // namespace dentra
