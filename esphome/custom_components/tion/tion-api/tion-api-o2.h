#pragma once

#include <functional>

#include "tion-api-writer.h"
#include "tion-api-o2-internal.h"

namespace dentra {
namespace tion_o2 {

// returns response frame size including crc
size_t get_req_frame_size(uint8_t frame_type);

// returns response frame size including crc
size_t get_rsp_frame_size(uint8_t frame_type);

class TionO2Api : public tion::TionApiBase, public tion::TionApiWriter {
 public:
  TionO2Api();

  void read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size);

  uint16_t get_state_type() const;

  bool reset_filter(const tion::TionState &state, uint32_t request_id = 1) const;
  bool factory_reset(const tion::TionState &state, uint32_t request_id = 1) const;
  bool reset_errors(const tion::TionState &state, uint32_t request_id = 1) const;

  bool set_work_mode(WorkModeFlags work_mode) const;

  void request_state() override;
  void write_state(tion::TionStateCall *call) override;
  void reset_filter() override { this->reset_filter(this->state_); }
  /// отображение режима MA_CONNECTED и MA_AUTO на дисплее бризера.
  /// для того чтобы исключить моргание, необходимо вызывать не реже чем раз в 200мс.
  void update_work_mode();

 protected:
  bool request_connect_() const;
  bool request_dev_info_() const;
  bool request_dev_mode_() const;
  bool request_state_() const;

  void dump_state_(const tiono2_state_t &state) const;
  void update_state_(const tiono2_state_t &state);
  void update_dev_info_(const tiono2_dev_info_t &dev_info);
  void update_dev_mode_(const DevModeFlags &dev_mode);
};

}  // namespace tion_o2
}  // namespace dentra
