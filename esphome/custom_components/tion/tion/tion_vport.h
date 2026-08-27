#pragma once
#include <type_traits>

#include "esphome/core/application.h"
#include "esphome/core/defines.h"

#include "esphome/components/vport/vport.h"

#include "../tion-api/tion-api-protocol.h"
#include "../tion-api/tion-api-writer.h"

namespace esphome {
namespace tion {

enum TionVPortType : uint8_t { VPORT_UNKNOWN = 0, VPORT_BLE, VPORT_UART, VPORT_JTAG, VPORT_TCP };

template<class protocol_type> class TionIO {
  static_assert(std::is_base_of_v<dentra::tion::TionProtocol<typename protocol_type::frame_spec_type>, protocol_type>,
                "protocol_type must derived from dentra::tion::TionProtocol class");

 public:
  using frame_spec_type = typename protocol_type::frame_spec_type;
  using on_frame_type = typename protocol_type::reader_type;

  void write(const frame_spec_type &data, size_t size) {
    this->protocol_.write_frame(data.type, data.data, size - frame_spec_type::head_size());
  }

  void set_on_frame(on_frame_type &&reader) { protocol_.reader = std::move(reader); }

 protected:
  protocol_type protocol_;
};

// vport wrapper with api support.
template<class frame_spec_t, class api_t> class TionVPortApi : public api_t, public vport::VPortListener<frame_spec_t> {
  static_assert(std::is_base_of_v<dentra::tion::TionApiWriter, api_t>, "api_t is not TionApiWriter");

 public:
  using vport_t = vport::VPort<frame_spec_t>;

  TionVPortApi(vport_t *vport) : vport_(vport) {
    vport->add_listener(this);
    using this_t = std::remove_pointer_t<decltype(this)>;
    api_t::set_writer(api_t::writer_type::template create<this_t, &this_t::write_frame_>(*this));
  }

  void on_ready() override { this->on_ready_fn.call_if(); }

  void on_frame(const frame_spec_t &frame, size_t size) override {
    this->read_frame(frame.type, frame.data, size - frame_spec_t::head_size());
  }

 protected:
  vport_t *vport_;

  bool write_frame_(uint16_t type, const void *data, size_t size) {
    uint8_t buf[sizeof(frame_spec_t) + size];
    std::memset(buf, 0, sizeof(buf));
    auto frame = reinterpret_cast<frame_spec_t *>(buf);
    frame->type = type;
    std::memcpy(frame->data, data, size);
    this->vport_->write(*frame, sizeof(buf));
    return true;
  }
};

}  // namespace tion
}  // namespace esphome
