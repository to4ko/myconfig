#pragma once

#include "tion-api.h"

namespace dentra {
namespace tion {

#pragma pack(push, 1)

// NOLINTNEXTLINE(readability-identifier-naming)
struct tion_dev_info_t {
  // NOLINTNEXTLINE(readability-identifier-naming)
  enum work_mode_t : uint8_t {
    // обычный режим работы
    NORMAL = 1,
    // бризер находится в режиме обновления
    UPDATE = 2,
  } work_mode;
  // NOLINTNEXTLINE(readability-identifier-naming)
  enum device_type_t : uint32_t {
    // Tion IQ 200
    IQ200 = 0x8001,
    // Tion Lite
    BRLT = 0x8002,
    // Tion 4S
    BR4S = 0x8003,
  } device_type;
  uint16_t firmware_version;
  uint16_t hardware_version;
  uint8_t reserved[16];
};

// NOLINTNEXTLINE(readability-identifier-naming)
template<size_t _AK> struct tion_state_counters_t {
  constexpr static size_t AK = _AK;
  // Motor time counter in seconds. power_up_time
  uint32_t work_time;
  // Electronics time count in seconds.
  uint32_t fan_time;
  // Filter time counter in seconds.
  uint32_t filter_time;
  // Airflow counter, m3=airflow_counter * 15.0 / 3600.0. - 4S
  //                  m3=airflow_counter * 10.0 / 3600.0. - Lite
  uint32_t airflow_counter;
  // Calculated airflow in m3.
  float airflow() const { return this->airflow_mult(this->airflow_counter) / 3600.0f; }
  // Calculated filter days left in days
  uint32_t filter_time_left_d() const { return this->filter_time / (24 * 3600); }
  // Calculated work time in days.
  uint32_t work_time_days() const { return this->work_time / (24 * 3600); }
  // Calculate airflow in m3/h.
  float airflow_mult(float counter) const { return counter * this->airflow_k(); }
  constexpr float airflow_k() const { return _AK; }

  uint8_t calc_productivity(uint32_t prev_fan_time, uint32_t prev_airflow_counter) const {
    if (prev_fan_time == 0) {
      return 0;
    }
    const auto diff_time = this->fan_time - prev_fan_time;
    if (diff_time == 0) {
      return 0;
    }
    const auto diff_airflow = this->airflow_counter - prev_airflow_counter;
    // return (float(diff_airflow) / float(diff_time) * state.counters.airflow_k());
    return this->airflow_mult(float(diff_airflow) / float(diff_time));
  }

  uint8_t calc_productivity(const TionState &state) const {
    return this->calc_productivity(state.fan_time, state.airflow_counter);
  }
};

#pragma pack(pop)

}  // namespace tion
}  // namespace dentra
