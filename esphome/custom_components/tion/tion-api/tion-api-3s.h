#pragma once

#include <functional>

#include "tion-api-writer.h"
#include "tion-api-3s-internal.h"

namespace dentra {
namespace tion {

class Tion3sApi : public TionApiBase, public tion::TionApiWriter {
 public:
  Tion3sApi();

  void read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size);

  uint16_t get_state_type() const;

  bool pair() const;

  bool request_command4() const;

  void request_state() override { this->request_state_(); }
  void write_state(tion::TionStateCall *call) override { this->write_state_(this->make_write_state_(call)); }
  void reset_filter() override { this->reset_filter_(this->state_); }

 protected:
  bool request_state_() const;
  bool write_state_(const tion::TionState &state) const;
  bool reset_filter_(const tion::TionState &state) const;
  bool factory_reset_(const tion::TionState &state) const;

  void dump_state_(const tion_3s::tion3s_state_t &state) const;
  void update_state_(const tion_3s::tion3s_state_t &state);
};

}  // namespace tion
}  // namespace dentra
