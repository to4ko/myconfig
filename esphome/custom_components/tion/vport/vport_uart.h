#pragma once
#include "esphome/core/defines.h"
#ifdef USE_VPORT_UART

#include "esphome/core/component.h"

#include "vport_component.h"

namespace esphome {
namespace vport {

#define VPORT_UART_LOG(port_name) VPORT_LOG(port_name)

// interface UartIO {
//   using reader_type = etl::delegate<void(const frame_spec_t &frame, size_t size)>;
//   void set_reader(reader_type &&reader);
//   void write(const uint8_t *data, size_t size);
//   void poll();
// };
template<class io_t, class frame_spec_t, class component_t>
class VPortUARTComponentImpl : public VPortIO<io_t, frame_spec_t>, public component_t {
  static_assert(std::is_base_of<Component, component_t>::value, "component_t must derived from Component class");

 public:
  explicit VPortUARTComponentImpl(io_t *io) : VPortIO<io_t, frame_spec_t>(io) {}

  void call_setup() override {
    component_t::call_setup();
    if (!this->is_failed()) {
      this->defer([this] { this->fire_ready(); });
    }
  }

  void loop() override {
    component_t::loop();
    this->io_->poll();
  }

  // required by VPortQComponent
  using io_type = io_t;
  using frame_spec_type = frame_spec_t;

 protected:
  void q_free_connection_() {}
  bool q_make_connection_() { return true; }
};

template<class io_t, class frame_spec_t, class component_t = Component>
using VPortUARTComponent = VPortQComponent<VPortUARTComponentImpl<io_t, frame_spec_t, component_t>>;

}  // namespace vport
}  // namespace esphome
#endif  // USE_VPORT_UART
