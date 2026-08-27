#pragma once

#include <functional>

#include "tion-api-writer.h"
#include "tion-api-4s-internal.h"

namespace dentra {
namespace tion_4s {

class Tion4sApi : public tion::TionApiBase, public tion::TionApiWriter {
  /// Callback listener for response to request_turbo command request.
  using on_turbo_type = etl::delegate<void(const tion4s_turbo_t &turbo, uint32_t request_id)>;
#ifdef TION_ENABLE_SCHEDULER
  /// Callback listener for response to request_time command request.
  using on_time_type = etl::delegate<void(time_t time, uint32_t request_id)>;
  /// Callback listener for response to request_timer command request.
  using on_timer_type = etl::delegate<void(uint8_t timer_id, const tion4s_timer_t &timers_state, uint32_t request_id)>;
  /// Callback listener for response to request_timers_state command request.
  using on_timers_state_type = etl::delegate<void(const tion4s_timers_state_t &timers_state, uint32_t request_id)>;
#endif

 public:
  Tion4sApi();

  void read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size);

  uint16_t get_state_type() const;

  bool write_state(const tion::TionState &state, uint32_t request_id) const;
  bool reset_filter(const tion::TionState &state, uint32_t request_id = 1) const;
  bool factory_reset(const tion::TionState &state, uint32_t request_id = 1) const;
  bool reset_errors(const tion::TionState &state, uint32_t request_id = 1) const;

  /// Callback listener for response to request_turbo command request.
  on_turbo_type on_turbo{};
  bool set_turbo(uint16_t time, uint32_t request_id = 1) const;
  bool request_turbo() const { return this->request_turbo_(); }

#ifdef TION_ENABLE_HEARTBEAT
  bool send_heartbeat() const;
#endif

#ifdef TION_ENABLE_SCHEDULER
  bool request_time(uint32_t request_id) const;
  void request_time() { this->request_time(++this->request_id_); }

  /// Callback listener for response to request_time command request.
  on_time_type on_time{};
  bool set_time(time_t time, uint32_t request_id) const;

  /// Callback listener for response to request_timer command request.
  on_timer_type on_timer{};
  bool request_timer(uint8_t timer_id, uint32_t request_id) const;
  void request_timer(uint8_t timer_id) { this->request_timer(timer_id, ++this->request_id_); }

  /// Request all timers.
  bool request_timers(uint32_t request_id = 1) const;

  bool write_timer(uint8_t timer_id, const tion4s_timer_t &timer, uint32_t request_id) const;
  void write_timer(uint8_t timer_id, const tion4s_timer_t &timer) {
    this->write_timer(timer_id, timer, ++this->request_id_);
  }

  bool request_timers_state(uint32_t request_id) const;
  void request_timers_state() { this->request_timers_state(++this->request_id_); }
  /// Callback listener for response to request_timers_state command request.
  on_timers_state_type on_timers_state{};

#endif
#ifdef TION_ENABLE_DIAGNOSTIC
  bool request_errors() const;
  bool request_test() const;
#endif

  void enable_native_boost_support();
  void request_state() override;
  void write_state(tion::TionStateCall *call) override {
    this->write_state(this->make_write_state_(call), ++this->request_id_);
  }
  void reset_filter() override { this->reset_filter(this->state_, ++this->request_id_); }

 protected:
  void boost_enable_native_(bool state) override;

  bool request_turbo_() const;
  bool request_dev_info_() const;
  bool request_state_() const;

  void dump_state_(const tion4s_state_t &state) const;
  void update_state_(const tion4s_state_t &state);
  void update_dev_info_(const tion::tion_dev_info_t &dev_info);
  void update_turbo_(const tion4s_turbo_t &turbo);
};

}  // namespace tion_4s
}  // namespace dentra
