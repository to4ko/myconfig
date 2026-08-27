#pragma once
#include "esphome/core/defines.h"
#ifdef USE_VPORT_UART

#ifdef USE_TION_HALF_DUPLEX
// #pragma message("USE_TION_HALF_DUPLEX")
#include "esphome/core/application.h"
#endif

#include "esphome/components/uart/uart_component.h"
#include "esphome/components/vport/vport_uart.h"

#include "../tion-api/tion-api-uart.h"

#include "tion_vport.h"

namespace esphome {
namespace tion {

template<class protocol_t> class TionUartIO : public TionIO<protocol_t>, public dentra::tion::TionUartReader {
 public:
  explicit TionUartIO(uart::UARTComponent *uart) : uart_(uart) {
    using this_t = std::remove_pointer_t<decltype(this)>;
    this->protocol_.writer.template set<this_t, &this_t::write_>(*this);
  }

  void poll() { this->protocol_.read_uart_data(this); }

  int available() override { return this->uart_->available(); }
  bool read_array(void *data, size_t size) override {
    return this->uart_->read_array(static_cast<uint8_t *>(data), size);
  }

 protected:
  uart::UARTComponent *uart_;
  bool write_(const uint8_t *data, size_t size) {
    this->uart_->write_array(data, size);
    this->uart_->flush();
    return true;
  }
};

template<class io_t, class component_t = Component>
class TionVPortUARTComponent : public vport::VPortUARTComponent<io_t, typename io_t::frame_spec_type, component_t> {
  using super_t = vport::VPortUARTComponent<io_t, typename io_t::frame_spec_type, component_t>;

 public:
  explicit TionVPortUARTComponent(io_t *io) : super_t(io) {
#ifdef USE_TION_HALF_DUPLEX
    using this_t = typename std::remove_pointer_t<decltype(this)>;
    this->io_->set_on_frame(io_t::on_frame_type::template create<this_t, &this_t::on_frame_>(*this));
#endif
  }

  TionVPortType get_type() const { return TionVPortType::VPORT_UART; }

  void call_setup() override {
    super_t::call_setup();
    // cleanup all existing data
    while (this->io_->available()) {
      uint8_t c;
      this->io_->read_array(&c, sizeof(c));
    }
  }

#ifdef USE_TION_HALF_DUPLEX
  void write(const typename io_t::frame_spec_type &frame, size_t size) override {
    if (this->await_frame_) {
      auto data8 = reinterpret_cast<const uint8_t *>(&frame);
      auto datav = std::vector<uint8_t>(data8, data8 + size);
      this->defer([this, datav]() {
        auto frame = reinterpret_cast<const typename io_t::frame_spec_type *>(datav.data());
        if (this->await_frame_) {
          ESP_LOGW("tion_vport_uart", "prev frame was not recv, may lead to crash");
        }
        super_t::write(*frame, datav.size());
        arch_feed_wdt();
        yield();
      });
    } else {
      this->await_frame_ = true;
      super_t::write(frame, size);
      arch_feed_wdt();
      yield();
    }
  }

 protected:
  bool await_frame_{};
  void on_frame_(const typename io_t::frame_spec_type &frame, size_t size) {
    arch_feed_wdt();
    yield();
    this->await_frame_ = false;
    this->fire_frame(frame, size);
  }
#endif
};

}  // namespace tion
}  // namespace esphome
#endif  // USE_VPORT_UART
