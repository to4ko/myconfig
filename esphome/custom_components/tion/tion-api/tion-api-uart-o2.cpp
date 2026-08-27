#include <cstring>
#include <cinttypes>

#include "log.h"
#include "utils.h"
// #include "tion-api-o2-internal.h"
#include "tion-api-uart-o2.h"

namespace dentra {
namespace tion_o2 {

static const char *const TAG = "tion-api-uart-o2";

TionO2UartProtocol::TionO2UartProtocol(bool is_proxy) {
  this->get_frame_size = is_proxy ? get_req_frame_size : get_rsp_frame_size;
}

void TionO2UartProtocol::read_uart_data(tion::TionUartReader *io) {
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

void TionO2UartProtocol::skip_uart_data_(tion::TionUartReader *io) {
  uint8_t buf[1];
  // read out all uart data, so we can start from a new command from some delay
  while (io->available()) {
    io->read_array(buf, 1);
    TION_LOGV(TAG, "Skipped %02X", *buf);
  }
  this->frame_size_ = 0;
}

int TionO2UartProtocol::read_frame_(tion::TionUartReader *io) {
  auto *frame = reinterpret_cast<tion::tion_any_frame_t *>(this->buf_);

  if (this->frame_size_ == 0) {
    if (!io->read_array(&frame->type, 1)) {
      TION_LOGW(TAG, "Failed read frame type");
      return READ_NEXT_LOOP;
    }

    this->frame_size_ = this->get_frame_size(frame->type);
    if (this->frame_size_ == 0) {
      TION_LOGW(TAG, "Unknown frame type [%02X]", frame->type);
      this->skip_uart_data_(io);
      return READ_NEXT_LOOP;
    }
  }

  if (io->available() < this->frame_size_) {
    TION_LOGD(TAG, "Waiting frame [%02X] data %i of %zu", frame->type, io->available(), this->frame_size_);
    return READ_NEXT_LOOP;
  }
  if (!io->read_array(frame->data, this->frame_size_)) {
    TION_LOGW(TAG, "Failed read frame [%02X] data", frame->type);
    this->skip_uart_data_(io);
    return READ_NEXT_LOOP;
  }

  auto data_size = this->frame_size_ - 1;  // 1 is crc at tail

  uint8_t crc = this->crc(this->crc(&frame->type, 1), frame->data, this->frame_size_);
  if (crc != 0) {
    TION_LOGW(TAG, "Invalid CRC %02x for frame [%02X] data %s", crc, frame->type,
              tion::hex_cstr(frame->data, data_size));
    this->skip_uart_data_(io);
    return READ_NEXT_LOOP;
  }

  TION_LOGV(TAG, "RX: [%02X]:%s", frame->type, tion::hex_cstr(frame->data, data_size));
  this->reader(*frame, data_size + frame->head_size());
  this->frame_size_ = 0;
  return READ_NEXT_LOOP;
}

bool TionO2UartProtocol::write_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  if (!this->writer) {
    TION_LOGE(TAG, "Writer is not configured");
    return false;
  }

  struct TionO2RawUartFrame {
    uint8_t type;
    uint8_t data[sizeof(uint8_t)];  // sizeof(uint8_t) is crc8 size
  } PACKED;

  auto frame_size = sizeof(TionO2RawUartFrame) + frame_data_size;
  if (frame_size > FRAME_MAX_SIZE) {
    TION_LOGW(TAG, "Frame size is to large: %zu", frame_size);
    return false;
  }

  uint8_t frame_buf[FRAME_MAX_SIZE]{};
  auto *frame = reinterpret_cast<TionO2RawUartFrame *>(frame_buf);
  frame->type = frame_type;
  if (frame_data_size > 0) {
    std::memcpy(frame->data, frame_data, frame_data_size);
  }
  uint8_t crc = this->crc(frame, frame_size - sizeof(crc));
  frame->data[frame_data_size] = crc;

  TION_LOGV(TAG, "TX: %s", tion::hex_cstr(frame_buf, frame_size));

  return this->writer(frame_buf, frame_size);
}

uint8_t TionO2UartProtocol::crc(uint8_t init, const void *data, size_t size) const {
  const uint8_t *data_ptr = static_cast<const uint8_t *>(data);
  const uint8_t *data_end = data_ptr + size;
  while (data_ptr < data_end) {
    init ^= *data_ptr++;
  }
  return init;
}

}  // namespace tion_o2
}  // namespace dentra
