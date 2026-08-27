#pragma once

#include <cstdint>
#include <vector>
#include "esphome/core/defines.h"

namespace esphome {
namespace vport {

#define VPORT_LOG(port_name) \
  ESP_LOGCONFIG(TAG, "Virtual %s port:", port_name); \
  if (this->command_interval_ == 0) { \
    ESP_LOGCONFIG(TAG, "  Command interval: disabled"); \
  } else { \
    ESP_LOGCONFIG(TAG, "  Command interval: %" PRIu32 " ms", this->command_interval_); \
  }

// TODO implement
// class VPortCodec {
//  public:
//   bool decode(const uint8_t *data, size_t size);
//   bool encode(const void *data, size_t size);
// };

template<typename frame_spec_t> class VPortListener {
  static_assert(std::is_class<frame_spec_t>::value, "frame_spec_t is not class");

 public:
  using frame_spec_type = frame_spec_t;

  /// Activated once connection estabilished.
  virtual void on_ready() {}
  /// Fired every time a frame is received.
  virtual void on_frame(const frame_spec_t &frame, size_t size) = 0;
};

class VPortBase {
 protected:
  void log_frame_(const void *data, size_t size);
  void log_write_(const void *data, size_t size);
};

template<class frame_spec_t> class VPort : public VPortBase {
  static_assert(std::is_class<frame_spec_t>::value, "frame_spec_t is not class");

 public:
  using frame_spec_type = frame_spec_t;

  void add_listener(VPortListener<frame_spec_t> *listener) {
    this->listeners_.push_back(listener);
    this->listeners_.shrink_to_fit();
  }

  void fire_frame(const frame_spec_t &frame, size_t size) {
    this->log_frame_(&frame, size);
    for (auto listener : this->listeners_) {
      listener->on_frame(frame, size);
    }
  }

  void fire_ready() {
    for (auto listener : this->listeners_) {
      listener->on_ready();
    }
  }

  virtual void write(const frame_spec_t &frame, size_t size) = 0;

 protected:
  std::vector<VPortListener<frame_spec_t> *> listeners_;
};

// interface IO {
//   using on_frame_type = etl::delegate<void(const frame_spec_t &frame, size_t size)>;
//   void set_on_frame(on_frame_type &&reader);
//   void write(const uint8_t *data, size_t size);
// };
template<class io_t, class frame_spec_t> class VPortIO : public VPort<frame_spec_t> {
  using vport_t = VPort<frame_spec_t>;

 public:
  explicit VPortIO(io_t *io) : io_(io) {
    this->io_->set_on_frame(io_t::on_frame_type::template create<vport_t, &vport_t::fire_frame>(*this));
  }

  void write(const frame_spec_t &frame, size_t size) override {
    this->log_write_(&frame, size);
    this->io_->write(frame, size);
  }

 protected:
  io_t *io_;
};

}  // namespace vport
}  // namespace esphome
