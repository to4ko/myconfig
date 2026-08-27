#pragma once
#include "esphome/core/defines.h"
#ifdef USE_VPORT_JTAG

#ifndef USE_ESP_IDF
#error "JTAG support requires ESP-IDF"
#endif

#include <driver/usb_serial_jtag.h>

#include "esphome/core/log.h"

#include "esphome/components/uart/uart_component.h"
#include "esphome/components/vport/vport_uart.h"

#include "../tion-api/tion-api-uart.h"

#include "tion_vport.h"

namespace esphome {
namespace tion {

// bool usb_serial_jtag_is_connected(void);

template<class protocol_t> class TionJtagIO : public TionIO<protocol_t>, public dentra::tion::TionUartReader {
 public:
  explicit TionJtagIO() {
    using this_t = std::remove_pointer_t<decltype(this)>;
    this->protocol_.writer.template set<this_t, &this_t::write_>(*this);
  }

  void poll() { this->protocol_.read_uart_data(this); }

  int available() override {
    if (this->is_failed_) {
      return 0;
    }
    if (this->buf_len_ < sizeof(this->buf_)) {
      const auto len = sizeof(this->buf_) - this->buf_len_;
      const auto read = usb_serial_jtag_read_bytes(this->buf_ + this->buf_len_, len, 0);
      if (read > 0) {
        ESP_LOGD("JTAG", "AV: len: %zu, rx: %d, data: %s", this->buf_len_, read,
                 format_hex_pretty(this->buf_, this->buf_len_ + read).c_str());
        this->buf_len_ = this->buf_len_ + read;
      }
    }
    return this->buf_len_;
  }
  bool read_array(void *data, size_t size) override {
    if (this->is_failed_) {
      return false;
    }
    auto *buf = static_cast<uint8_t *>(data);
    if (this->buf_len_) {
      const auto cpy_len = std::min(this->buf_len_, size);
      ESP_LOGD("JTAG", "RX1: siz: %u, cpy: %u data: %s", size, cpy_len,
               format_hex_pretty(this->buf_, this->buf_len_).c_str());
      std::memcpy(buf, this->buf_, cpy_len);
      buf += cpy_len;
      size -= cpy_len;
      const auto buf_len = this->buf_len_ - cpy_len;
      std::memmove(this->buf_, this->buf_ + cpy_len, buf_len);
      this->buf_len_ = buf_len;
      ESP_LOGD("JTAG", "RX2: data: %s", format_hex_pretty(this->buf_, this->buf_len_).c_str());
    }
    if (size == 0) {
      return true;
    }
    return usb_serial_jtag_read_bytes(buf, size, 0) == size;
  }

  void mark_failed() { this->is_failed_ = true; }

 protected:
  uint8_t buf_[256]{};
  size_t buf_len_{};
  bool is_failed_{};

  bool write_(const uint8_t *data, size_t size) {
    if (this->is_failed_) {
      ESP_LOGD("JTAG", "jtag driver was not installed");
      return false;
    }
    const auto tx = usb_serial_jtag_write_bytes(data, size, 0);
    ESP_LOGD("JTAG", "TX: len: %d, %s", tx, format_hex_pretty(data, size).c_str());
    return tx == size;
  }
};

template<class io_t, class component_t = Component>
class TionVPortJTAGComponent : public vport::VPortUARTComponent<io_t, typename io_t::frame_spec_type, component_t> {
  using super_t = vport::VPortUARTComponent<io_t, typename io_t::frame_spec_type, component_t>;

 public:
  explicit TionVPortJTAGComponent(io_t *io) : super_t(io) {}

  void call_setup() override {
    usb_serial_jtag_driver_config_t config{
        .tx_buffer_size = 256,
        .rx_buffer_size = 256,
    };
    esp_err_t err = usb_serial_jtag_driver_install(&config);
    if (err != ESP_OK) {
      this->mark_failed();
      this->io_->mark_failed();
    }
  }

  TionVPortType get_type() const { return TionVPortType::VPORT_UART; }
};

}  // namespace tion
}  // namespace esphome

#endif  // USE_VPORT_JTAG
