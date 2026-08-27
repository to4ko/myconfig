#include <cstring>
#include <cinttypes>

#include "log.h"
#include "utils.h"
#include "tion-api-3s-internal.h"  //tion_3s::tion3s_frame_t::FRAME_DATA_SIZE
#include "tion-api-uart-3s.h"

namespace dentra {
namespace tion {

using namespace tion_3s;

static const char *const TAG = "tion-api-uart-3s";

#pragma pack(push, 1)
struct Tion3sRawUartFrame {
  union {
    struct {
      uint8_t head;
      uint8_t type;
      uint8_t data[tion_3s::tion3s_frame_t::FRAME_DATA_SIZE];
    } rx;
    tion_frame_t<uint8_t[tion_3s::tion3s_frame_t::FRAME_DATA_SIZE]> data;
  };
  uint8_t magic;
};
#pragma pack(pop)

void Tion3sUartProtocol::read_uart_data(TionUartReader *io) {
  if (!this->reader) {
    TION_LOGE(TAG, "Reader is not configured");
    return;
  }

  while (io->available() > 0) {
    if (this->read_frame_(io) == READ_NEXT_LOOP) {
      break;
    }
    tion::yield();
  }
}

Tion3sUartProtocol::read_frame_result_t Tion3sUartProtocol::read_frame_(TionUartReader *io) {
  auto *frame = reinterpret_cast<Tion3sRawUartFrame *>(this->buf_);

  if (frame->rx.head != this->head_type_) {
    if (io->available() < sizeof(frame->rx.head)) {
      // do not flood log while waiting magic
      // TION_LOGV(TAG, "Waiting frame magic");
      return READ_NEXT_LOOP;
    }
    if (!io->read_array(&frame->rx.head, sizeof(frame->rx.head))) {
      TION_LOGW(TAG, "Failed read frame head");
      return READ_THIS_LOOP;
    }
    if (frame->rx.head != this->head_type_) {
      TION_LOGW(TAG, "Unexpected byte: 0x%02X", frame->rx.head);
      return READ_THIS_LOOP;
    }
  }

  if (frame->rx.type == 0) {
    if (io->available() < sizeof(frame->rx.type)) {
      TION_LOGV(TAG, "Waiting frame type");
      return READ_NEXT_LOOP;
    }
    if (!io->read_array(&frame->rx.type, sizeof(frame->rx.type))) {
      TION_LOGW(TAG, "Failed read frame type");
      this->reset_buf_();
      return READ_THIS_LOOP;
    }
  }

  constexpr uint32_t tail_size = sizeof(frame->rx.data) + sizeof(frame->magic);
  if (io->available() < tail_size) {
    TION_LOGV(TAG, "Waiting frame data %i of %" PRIu32, io->available(), tail_size);
    return READ_NEXT_LOOP;
  }

  if (!io->read_array(&frame->rx.data, tail_size)) {
    TION_LOGW(TAG, "Failed read frame data");
    this->reset_buf_();
    return READ_THIS_LOOP;
  }

  TION_LOGV(TAG, "RX: %s", hex_cstr(&frame->data, sizeof(frame->data)));

  if (frame->magic != FRAME_MAGIC_END) {
    TION_LOGW(TAG, "Invalid frame magic %02X", frame->magic);
    this->reset_buf_();
    return READ_THIS_LOOP;
  }

  tion::yield();
  this->reader(*reinterpret_cast<const tion_any_frame_t *>(&frame->data), sizeof(frame->data));
  this->reset_buf_();

  return READ_NEXT_LOOP;
}

bool Tion3sUartProtocol::write_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  if (!this->writer) {
    TION_LOGE(TAG, "Writer is not configured");
    return false;
  }

  Tion3sRawUartFrame frame{.data = {.type = frame_type, .data = {}}, .magic = FRAME_MAGIC_END};
  if (frame_data_size <= sizeof(frame.data.data)) {
    std::memcpy(frame.data.data, frame_data, frame_data_size);
  }

  TION_LOGV(TAG, "TX: %s", tion::hex_cstr(reinterpret_cast<uint8_t *>(&frame), sizeof(frame)));

  return this->writer(reinterpret_cast<uint8_t *>(&frame), sizeof(frame));
}

}  // namespace tion
}  // namespace dentra
