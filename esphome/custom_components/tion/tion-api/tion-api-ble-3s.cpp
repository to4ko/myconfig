#include <utility>
#include <cstring>
#include <cstdlib>

#include "crc.h"
#include "utils.h"
#include "log.h"

#include "tion-api-3s.h"           // FRAME_MAGIC_END
#include "tion-api-3s-internal.h"  // tion3s_frame_t::FRAME_DATA_SIZE

#include "tion-api-ble-3s.h"

namespace dentra {
namespace tion {

using namespace tion_3s;

static const char *const TAG = "tion-api-ble-3s";

#pragma pack(push, 1)
struct Tion3sRawBleFrame {
  enum : uint8_t { FRAME_MAGIC = FRAME_MAGIC_END };
  tion_frame_t<uint8_t[tion_3s::tion3s_frame_t::FRAME_DATA_SIZE]> data;
  uint8_t magic;
};
#pragma pack(pop)

const char *Tion3sBleProtocol::get_ble_service() const { return "6e400001-b5a3-f393-e0a9-e50e24dcca9e"; }
const char *Tion3sBleProtocol::get_ble_char_tx() const { return "6e400002-b5a3-f393-e0a9-e50e24dcca9e"; };
const char *Tion3sBleProtocol::get_ble_char_rx() const { return "6e400003-b5a3-f393-e0a9-e50e24dcca9e"; }

// TODO remove return type
bool Tion3sBleProtocol::read_data(const uint8_t *data, size_t size) {
  TION_LOGV(TAG, "Read data: %s", hex_cstr(data, size));
  if (!this->reader) {
    TION_LOGE(TAG, "Reader is not configured");
    return false;
  }
  if (data == nullptr || size == 0) {
    TION_LOGW(TAG, "Empty frame data");
    return false;
  }
  if (size != sizeof(Tion3sRawBleFrame)) {
    TION_LOGW(TAG, "Invalid frame size %zu", size);
    return false;
  }
  const auto *frame = reinterpret_cast<const Tion3sRawBleFrame *>(data);
  if (frame->magic != Tion3sRawBleFrame::FRAME_MAGIC) {
    TION_LOGW(TAG, "Invalid frame magic %02X", frame->magic);
    return false;
  }
  this->reader(*reinterpret_cast<const tion_any_frame_t *>(&frame->data), sizeof(frame->data));
  return true;
}

bool Tion3sBleProtocol::write_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  if (!this->writer) {
    TION_LOGE(TAG, "Writer is not configured");
    return false;
  }
  Tion3sRawBleFrame frame{.data = {.type = frame_type, .data = {}}, .magic = Tion3sRawBleFrame::FRAME_MAGIC};
  if (frame_data_size <= sizeof(frame.data.data)) {
    std::memcpy(frame.data.data, frame_data, frame_data_size);
  }
  return this->writer(reinterpret_cast<const uint8_t *>(&frame), sizeof(frame));
}

}  // namespace tion
}  // namespace dentra
