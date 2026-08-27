#include <cmath>
#include <cinttypes>

#include "log.h"
#include "utils.h"
#include "tion-api-lt.h"
#include "tion-api-defines.h"

namespace dentra {
namespace tion {

static const char *const TAG = "tion-api-lt";

}
}  // namespace dentra

namespace dentra {
namespace tion_lt {
constexpr size_t ERRORS_COUNT = tionlt_state_t::ERROR_MAX_BIT - tionlt_state_t::ERROR_MIN_BIT + 1;
static const char *const ERRORS[ERRORS_COUNT] = {
    // EC01
    "Ошибка в работе заслонки",
    // EC02
    "Ошибка в работе заслонки",
    // EC03
    "Ошибка в работе заслонки",
    // EC04
    "Ошибка работы нагревателя",
    // EC05
    "Ошибка работы нагревателя",
    // EC06
    "Ошибка работы нагревателя",
    // EC07
    "Ошибка измерения температуры",
    // EC08
    "Ошибка измерения температуры",
    // EC09
    "Ошибка измерения температуры",
    // EC10
    "Ошибка измерения температуры",
    // EC11
    "Ошибка работы нагревателя",
};

constexpr size_t WARNINGS_COUNT = tionlt_state_t::WARNING_MAX_BIT - tionlt_state_t::WARNING_MIN_BIT + 1;
static const char *const WARNINGS[WARNINGS_COUNT] = {
    // WS01
    "Температура поступающего воздуха выше допустимого значения",
    // WS02
    "Температура поступающего воздуха ниже допустимого значения",
    // WS03
    "Температура платы управления выше допустимого значения",
    // WS04
    "Температура платы управления ниже допустимого значения",
};

void tionlt_state_t::report_errors(uint32_t errors) {
  tion::enum_errors(errors, tionlt_state_t::ERROR_MIN_BIT, tionlt_state_t::ERROR_MAX_BIT, nullptr,
                    [](uint8_t err, const void *) {
                      if (err > 0 && (err - 1) < ERRORS_COUNT) {
                        TION_REPORT_EC(tion::TAG, err, ERRORS[err - 1]);
                      } else {
                        TION_REPORT_EC_UNK(tion::TAG, err);
                      }
                    });
  tion::enum_errors(errors, tionlt_state_t::WARNING_MIN_BIT, tionlt_state_t::WARNING_MAX_BIT, nullptr,
                    [](uint8_t err, const void *) {
                      if (err > 0 && (err - 1) < WARNINGS_COUNT) {
                        TION_REPORT_WS(tion::TAG, err, WARNINGS[err - 1]);
                      } else {
                        TION_REPORT_WS_UNK(tion::TAG, err);
                      }
                    });
}

}  // namespace tion_lt
}  // namespace dentra

namespace dentra {
namespace tion {

using tion::TionTraits;
using tion::TionState;
using tion_lt::tionlt_state_t;
using tion_lt::tionlt_state_set_req_t;
using namespace tion_lt;

static const uint8_t PROD[] = {0, TION_LT_AUTO_PROD};

uint16_t TionLtApi::get_state_type() const { return FRAME_TYPE_STATE_RSP; }

void TionLtApi::read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  // do not use switch statement with non-contiguous values, as this will generate a lookup table with wasted space.
  if (frame_type == FRAME_TYPE_STATE_RSP) {
    // NOLINTNEXTLINE(readability-identifier-naming)
    if (frame_data_size != sizeof(tionlt_state_get_req_t)) {
      TION_LOGW(TAG, "Incorrect state response data size: %zu", frame_data_size);
    } else {
      const auto *frame = static_cast<const tionlt_state_get_req_t *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] State", frame->request_id);
      this->update_state_(frame->state);
      this->notify_state_(frame->request_id);
    }
    return;
  }

  if (frame_type == FRAME_TYPE_DEV_INFO_RSP) {
    if (frame_data_size != sizeof(tion_dev_info_t)) {
      TION_LOGW(TAG, "Incorrect device info response data: %s", hex_cstr(frame_data, frame_data_size));
    } else {
      TION_LOGD(TAG, "Response Device info");
      this->update_dev_info_(*static_cast<const tion_dev_info_t *>(frame_data));
    }
    return;
  }

  if (frame_type == FRAME_TYPE_AUTOKIV_PARAM_RSP) {
    TION_LOGD(TAG, "auto kiv param response: %s", hex_cstr(frame_data, frame_data_size));
    return;
  }

  TION_LOGW(TAG, "Unsupported frame type 0x%04X: %s", frame_type, hex_cstr(frame_data, frame_data_size));
}

bool TionLtApi::request_dev_info_() const {
  TION_LOGD(TAG, "Request device info");
  return this->write_frame(FRAME_TYPE_DEV_INFO_REQ);
}

bool TionLtApi::request_state_() const {
  TION_LOGD(TAG, "Request state");
  return this->write_frame(FRAME_TYPE_STATE_REQ);
}

bool TionLtApi::write_state(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Write state", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tionlt_state_set_req_t st_set(state, this->button_presets_, request_id);
  this->fix_st_set_(&st_set);
  TION_DUMP(TAG, "req  : %" PRIu32, st_set.request_id);
  TION_DUMP(TAG, "power: %s", ONOFF(st_set.data.power_state));
  TION_DUMP(TAG, "sound: %s", ONOFF(st_set.data.sound_state));
  TION_DUMP(TAG, "led  : %s", ONOFF(st_set.data.led_state));
  TION_DUMP(TAG, "auto : %s", ONOFF(st_set.data.ma_auto));
  TION_DUMP(TAG, "heat : %s", ONOFF(st_set.data.heater_state));
  TION_DUMP(TAG, "gate : %s", st_set.data.gate_state == tionlt_state_t::GateState::OPENED ? "opened" : "closed");
  TION_DUMP(TAG, "temp : %u", st_set.data.target_temperature);
  TION_DUMP(TAG, "fan  : %u", st_set.data.fan_speed);
  TION_DUMP(TAG, "btn_p: %d/%d/%d, %d/%d/%d °C",                                   //-//
            st_set.data.button_presets.fan[0], st_set.data.button_presets.fan[1],  //-//
            st_set.data.button_presets.fan[2], st_set.data.button_presets.tmp[0],  //-//
            st_set.data.button_presets.tmp[1], st_set.data.button_presets.tmp[2]);
  return this->write_frame(FRAME_TYPE_STATE_SET, st_set);
}

bool TionLtApi::reset_filter(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Reset filter", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tionlt_state_set_req_t st_set(state, this->button_presets_, request_id);
  st_set.data.filter_reset = true;
  st_set.data.filter_time = 181;
  this->fix_st_set_(&st_set);
  return this->write_frame(FRAME_TYPE_STATE_SET, st_set);
}

bool TionLtApi::factory_reset(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Factory reset", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tionlt_state_set_req_t st_set(state, this->button_presets_, request_id);
  st_set.data.factory_reset = true;
  this->fix_st_set_(&st_set);
  return this->write_frame(FRAME_TYPE_STATE_SET, st_set);
}

bool TionLtApi::reset_errors(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Error reset", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tionlt_state_set_req_t st_set(state, this->button_presets_, request_id);
  st_set.data.error_reset = true;
  this->fix_st_set_(&st_set);
  return this->write_frame(FRAME_TYPE_STATE_SET, st_set);
}

void TionLtApi::fix_st_set_(tionlt_state_set_req_t *set) const {
  if (set->data.fan_speed != 0) {
    return;
  }
  if (!this->traits_.supports_kiv) {
    set->data.fan_speed = 1;
    return;
  }
  // для предотвращения обморожения не разрешаем работу в режиме kiv если внешняя температура менее 5 °C
  if (this->state_.outdoor_temperature < 5) {
    set->data.fan_speed = 1;
    TION_LOGW(TAG, "KIV mode not supported when outdoor temperature less than 5 °C");
    return;
  }
  // не разрешаем работу в режиме kiv если включен обогреватель
  if (set->data.heater_state) {
    set->data.fan_speed = 1;
    TION_LOGW(TAG, "KIV mode not supported when heater is on");
    return;
  }
}

void TionLtApi::request_state() {
  if (this->state_.firmware_version == 0) {
    this->request_dev_info_();
  }
  this->request_state_();
}

TionLtApi::TionLtApi() {
  this->traits_.errors_decode = tionlt_state_t::decode_errors;
  this->traits_.errors_report = tionlt_state_t::report_errors;

  this->traits_.supports_heater_var = true;
  this->traits_.supports_work_time = true;
  this->traits_.supports_airflow_counter = true;
  this->traits_.supports_fan_time = true;
  this->traits_.supports_led_state = true;
  this->traits_.supports_sound_state = true;
  this->traits_.supports_pcb_ctl_temperature = true;
  this->traits_.supports_reset_filter = true;
  this->traits_.max_heater_power = TION_LT_HEATER_POWER;
  this->traits_.max_fan_speed = 6;
  this->traits_.min_target_temperature = TION_MIN_TEMPERATURE;
  this->traits_.max_target_temperature = TION_MAX_TEMPERATURE;

  this->traits_.max_fan_power[0] = TION_LT_MAX_FAN_POWER0;
  this->traits_.max_fan_power[1] = TION_LT_MAX_FAN_POWER1;
  this->traits_.max_fan_power[2] = TION_LT_MAX_FAN_POWER2;
  this->traits_.max_fan_power[3] = TION_LT_MAX_FAN_POWER3;
  this->traits_.max_fan_power[4] = TION_LT_MAX_FAN_POWER4;
  this->traits_.max_fan_power[5] = TION_LT_MAX_FAN_POWER5;
  this->traits_.max_fan_power[6] = TION_LT_MAX_FAN_POWER6;

  this->traits_.auto_prod = PROD;
}

void TionLtApi::update_dev_info_(const tion::tion_dev_info_t &dev_info) {
  this->state_.firmware_version = dev_info.firmware_version;
  this->state_.hardware_version = dev_info.hardware_version;
}

void TionLtApi::update_state_(const tionlt_state_t &state) {
  this->state_.initialized = true;

  this->state_.power_state = state.power_state;
  this->state_.heater_state = state.heater_state;
  this->state_.sound_state = state.sound_state;
  this->state_.led_state = state.led_state;
  this->state_.comm_source = state.comm_source;
  this->state_.auto_state = state.ma_auto;
  this->state_.filter_state = state.filter_state;
  this->state_.gate_error_state = (state.errors & tionlt_state_t::GATE_ERROR_BIT) != 0;
  this->state_.gate_position = state.gate_state ? TionGatePosition::OPENED : TionGatePosition::CLOSED;
  this->state_.fan_speed = state.fan_speed;
  this->state_.outdoor_temperature = state.outdoor_temperature;
  this->state_.current_temperature = state.current_temperature;
  this->state_.target_temperature = state.target_temperature;
  this->state_.productivity = state.counters.calc_productivity(this->state_);
  this->state_.heater_var = state.heater_var;
  this->state_.work_time = state.counters.work_time;
  this->state_.fan_time = state.counters.fan_time;
  this->state_.filter_time_left = state.counters.filter_time;
  this->state_.airflow_counter = state.counters.airflow_counter;
  this->state_.airflow_m3 = state.counters.airflow();
  this->traits_.max_heater_power = state.heater_present ? TION_LT_HEATER_POWER : 0;
  this->traits_.max_fan_speed = state.max_fan_speed;
  // this->traits_.min_target_temperature = -30;
  // this->traits_.min_target_temperature = 25;
  // this->state_.hardware_version = dev_info.hardware_version;
  // this->state_.firmware_version = dev_info.firmware_version;
  this->state_.pcb_ctl_temperature = state.pcb_temperature;
  // this->state_.pcb_pwr_temperature = 0;
  this->state_.errors = state.errors;

  this->dump_state_(state);
}

void TionLtApi::dump_state_(const tionlt_state_t &state) const {
  this->state_.dump(TAG, this->traits_);

  TION_DUMP(TAG, "gate_state  : %u", state.gate_state);
  TION_DUMP(TAG, "heater_prsnt: %s", ONOFF(state.heater_present));
  TION_DUMP(TAG, "heater_var  : %u", state.heater_var);
  TION_DUMP(TAG, "kiv_present : %s", ONOFF(state.kiv_present));
  TION_DUMP(TAG, "kiv_active  : %s", ONOFF(state.kiv_active));
  TION_DUMP(TAG, "airflow_cnt : %" PRIu32, state.counters.airflow_counter);
  TION_DUMP(TAG, "btn_presets : %d/%d/%d, %d/%d/%d °C",                //-//
            state.button_presets.fan[0], state.button_presets.fan[1],  //-//
            state.button_presets.fan[2], state.button_presets.tmp[0],  //-//
            state.button_presets.tmp[1], state.button_presets.tmp[2]);
  TION_DUMP(TAG, "errors_cnt  : %s",
            format_hex_pretty(reinterpret_cast<const uint8_t *>(&state.errors_cnt), sizeof(state.errors_cnt)).c_str());
  TION_DUMP(TAG, "test_type   : 0x%02X (%s)", state.test_type, tion::get_flag_bits(state.test_type));
  TION_DUMP(TAG, "reserved    : 0x%02X (%s)", state.reserved, tion::get_flag_bits(state.reserved));
}

void TionLtApi::set_button_presets(const dentra::tion_lt::button_presets_t &button_presets) {
  this->button_presets_ = button_presets;
}

void TionLtApi::enable_kiv_support() { this->traits_.supports_kiv = true; }

}  // namespace tion
}  // namespace dentra
