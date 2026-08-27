#include <utility>
#include <cstring>
#include <cstdlib>

#include "crc.h"
#include "utils.h"
#include "log.h"

#include "tion-api-ble-lt.h"

namespace dentra {
namespace tion {

static const char *const TAG = "tion-api-ble-lt";

#pragma pack(push, 1)
struct TionLtRawBlePacket {
  enum {
    TYPE_NONE = 1,
    // first packet. 0x00
    TYPE_FRST = 0 << 6,
    // n-th packet. 0x40
    TYPE_CURR = 1 << 6,
    // first and last packet at the same time. 0x80
    TYPE_LONE = 2 << 6,
    // last packet 0xC0.
    TYPE_LAST = 3 << 6,
  };
  enum { MAX_MTU_SIZE = 20 };
  uint8_t type;
  uint8_t data[MAX_MTU_SIZE - 1];
};
struct TionLtRawBleFrame {
  enum { FRAME_MAGIC = 0x3A };
  uint16_t size;
  uint8_t magic;
  uint8_t random;                                    // always 0xAD
  tion_ble_frame_t<uint8_t[sizeof(uint16_t)]> data;  // sizeof(uint16_t) is crc16 size
};
#pragma pack(pop)

const char *TionLtBleProtocol::get_ble_service() const { return "98f00001-3788-83ea-453e-f52244709ddb"; }
const char *TionLtBleProtocol::get_ble_char_tx() const { return "98f00002-3788-83ea-453e-f52244709ddb"; };
const char *TionLtBleProtocol::get_ble_char_rx() const { return "98f00003-3788-83ea-453e-f52244709ddb"; }

bool TionLtBleProtocol::read_data(const uint8_t *data, size_t size) {
  TION_LOGV(TAG, "Read packet: %s", hex_cstr(data, size));
  if (data == nullptr || size == 0) {
    TION_LOGW(TAG, "Packet is empty");
    return false;
  }

  auto *pkt = reinterpret_cast<const TionLtRawBlePacket *>(data);
  auto data_size = size - sizeof(pkt->type);

  if (pkt->type == TionLtRawBlePacket::TYPE_LONE) {
    TION_LOGV(TAG, "Packet LONE");
    this->read_frame_(pkt->data, data_size);
    return true;
  }

  if (pkt->type == TionLtRawBlePacket::TYPE_FRST) {
    TION_LOGV(TAG, "Packet FRST");
    this->rx_buf_.clear();
    this->rx_buf_.insert(this->rx_buf_.end(), pkt->data, pkt->data + data_size);
    return true;
  }

  if (pkt->type == TionLtRawBlePacket::TYPE_CURR) {
    TION_LOGV(TAG, "Packet CURR");
    this->rx_buf_.insert(this->rx_buf_.end(), pkt->data, pkt->data + data_size);
    return true;
  }

  if (pkt->type == TionLtRawBlePacket::TYPE_LAST) {
    TION_LOGV(TAG, "Packet LAST");
    this->rx_buf_.insert(rx_buf_.end(), pkt->data, pkt->data + data_size);
    this->read_frame_(this->rx_buf_.data(), this->rx_buf_.size());
    this->rx_buf_.clear();
    this->rx_buf_.shrink_to_fit();
    return true;
  }

  TION_LOGW(TAG, "Unknown packet type 0x%02X", pkt->type);
  return false;
}

// TODO remove return type
bool TionLtBleProtocol::read_frame_(const void *data, uint32_t size) {
  TION_LOGV(TAG, "Read frame: %s", hex_cstr(data, size));
  if (!this->reader) {
    TION_LOGE(TAG, "Reader is not configured");
    return false;
  }

  const TionLtRawBleFrame *frame = static_cast<const TionLtRawBleFrame *>(data);
  if (frame->magic != TionLtRawBleFrame::FRAME_MAGIC) {
    TION_LOGW(TAG, "Invalid frame magic: 0x%02X", frame->magic);
    return false;
  }
  if (frame->size != size) {
    TION_LOGW(TAG, "Invalid frame size: %u", frame->size);
    return false;
  }
  if (this->rx_crc_) {
    const uint16_t crc = crc16_ccitt_false_ffff(frame, size);
    if (crc != 0) {
      TION_LOGW(TAG, "Invalid frame crc: %04X", crc);
      return false;
    }
  }
  this->reader(*reinterpret_cast<const tion_any_ble_frame_t *>(&frame->data),
               frame->size - sizeof(TionLtRawBleFrame) + sizeof(tion_any_ble_frame_t));
  return true;
}

bool TionLtBleProtocol::write_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  TION_LOGV(TAG, "Write frame 0x%04X: %s", frame_type, hex_cstr(frame_data, frame_data_size));

  uint8_t tx_buf[frame_data_size + sizeof(TionLtRawBleFrame)];
  auto *tx_frame = reinterpret_cast<TionLtRawBleFrame *>(tx_buf);

  tx_frame->magic = TionLtRawBleFrame::FRAME_MAGIC;
  tx_frame->random = 0xAD;
  tx_frame->size = sizeof(tx_buf);
  tx_frame->data.type = frame_type;
  tx_frame->data.ble_request_id = 1;  // TODO возможно можно инкриминировать и проверять в ответе
  std::memcpy(tx_frame->data.data, frame_data, frame_data_size);

  uint16_t crc = __builtin_bswap16(crc16_ccitt_false_ffff(tx_frame, sizeof(tx_buf) - sizeof(crc)));
  std::memcpy(&tx_frame->data.data[frame_data_size], &crc, sizeof(crc));

  return this->write_packet_(tx_frame, sizeof(tx_buf));
}

bool TionLtBleProtocol::write_packet_(const void *data, uint16_t size) const {
  TION_LOGV(TAG, "Write BLE packet: %s", hex_cstr(data, size));

  if (!this->writer) {
    TION_LOGE(TAG, "Writer is not configured");
    return false;
  }

  TionLtRawBlePacket pkt;

  size_t data_packet_size = sizeof(pkt.data);
  const uint8_t *data_ptr = static_cast<const uint8_t *>(data);

  data_packet_size = size > data_packet_size ? data_packet_size : size;
  size -= data_packet_size;
  pkt.type = size ? TionLtRawBlePacket::TYPE_FRST : TionLtRawBlePacket::TYPE_LONE;
  std::memcpy(pkt.data, data_ptr, data_packet_size);
  data_ptr += data_packet_size;

  if (!this->writer(reinterpret_cast<uint8_t *>(&pkt), data_packet_size + sizeof(pkt.type))) {
    TION_LOGW(TAG, "Can't write packet");
    return false;
  }

  while (size) {
    data_packet_size = size > data_packet_size ? data_packet_size : size;
    size -= data_packet_size;
    pkt.type = size ? TionLtRawBlePacket::TYPE_CURR : TionLtRawBlePacket::TYPE_LAST;
    std::memcpy(pkt.data, data_ptr, data_packet_size);
    data_ptr += data_packet_size;

    if (!this->writer(reinterpret_cast<uint8_t *>(&pkt), data_packet_size + sizeof(pkt.type))) {
      TION_LOGW(TAG, "Can't write packet");
      return false;
    }
  }

  return true;
}

}  // namespace tion
}  // namespace dentra
