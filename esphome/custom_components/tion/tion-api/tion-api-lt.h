#pragma once

#include <functional>

#include "tion-api-writer.h"
#include "tion-api-lt-internal.h"
#include "tion-api-defines.h"

namespace dentra {
namespace tion {

class TionLtApi : public TionApiBase, public tion::TionApiWriter {
 public:
  TionLtApi();

  void read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size);

  uint16_t get_state_type() const;

  bool write_state(const TionState &state, uint32_t request_id) const;
  bool reset_filter(const TionState &state, uint32_t request_id = 1) const;
  bool factory_reset(const TionState &state, uint32_t request_id = 1) const;
  bool reset_errors(const TionState &state, uint32_t request_id = 1) const;

  void set_button_presets(const dentra::tion_lt::button_presets_t &button_presets);

  void request_state() override;
  void write_state(TionStateCall *call) override {
    this->write_state(this->make_write_state_(call), ++this->request_id_);
  }
  void reset_filter() override { this->reset_filter(this->state_, ++this->request_id_); }

  void enable_kiv_support();

 protected:
  tion_lt::button_presets_t button_presets_{
      .tmp{
          TION_LT_BUTTON_PRESET_TMP1,
          TION_LT_BUTTON_PRESET_TMP2,
          TION_LT_BUTTON_PRESET_TMP3,
      },
      .fan{
          TION_LT_BUTTON_PRESET_FAN1,
          TION_LT_BUTTON_PRESET_FAN2,
          TION_LT_BUTTON_PRESET_FAN3,
      },
  };

  bool request_dev_info_() const;
  bool request_state_() const;

  void dump_state_(const tion_lt::tionlt_state_t &state) const;
  void update_state_(const tion_lt::tionlt_state_t &state);
  void update_dev_info_(const tion::tion_dev_info_t &dev_info);

  void fix_st_set_(tion_lt::tionlt_state_set_req_t *set) const;
};

}  // namespace tion
}  // namespace dentra
