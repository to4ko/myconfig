#include <cstddef>
#include <cmath>
#include <cinttypes>

#include "log.h"
#include "utils.h"
#include "tion-api-4s.h"
#include "tion-api-defines.h"

namespace dentra {
namespace tion_4s {

static const char *const TAG = "tion-api-4s";

static const uint8_t PROD[] = {0, TION_4S_AUTO_PROD};

using tion::tion_dev_info_t;
using tion::TionGatePosition;
using tion::TionTraits;
using tion::TionState;

constexpr size_t ERRORS_COUNT = tion4s_state_t::ERROR_MAX_BIT - tion4s_state_t::ERROR_MIN_BIT + 1;
static const char *const ERRORS[ERRORS_COUNT] = {
    // EC01
    "При движении заслонки целевой концевой выключатель не меняет состояние в отличие от исходного",
    // EC02
    "При движении заслонки ни один концевой выключатель не меняет состояние",
    // EC03
    "Оба концевых выключателя замкнуты при отсутствии управляющего сигнала на силовой ключ заслонки",
    // EC04
    "Показания выходного датчика отличаются от целевой температуры на 3 °C "
    "и показания входного датчика меньше целевой температуры",
    // EC05
    "Показания выходного датчика меньше целевой температуры на 6 °C "
    "и показания входного датчика меньше целевой температуры",
    // EC06
    "Показания выходного датчика больше целевой температуры на 12 °C "
    "и показания входного датчика меньше целевой температуры",
    // EC07
    "Температура на выходе из устройства выше допустимой или замыкание на двух выходных датчиках",
    // EC08
    "Температура на выходе из устройства ниже допустимой или обрыв на двух выходных датчиках",
    // EC09
    "Температура на выходе из устройства выше допустимой или замыкание на одном выходном датчике",
    // EC10
    "Температура на выходе из устройства ниже допустимой или обрыв на одном выходном датчике",
    // EC11
    "Обрыв электрической цепи питания нагревателя",
};

constexpr size_t WARNINGS_COUNT = tion4s_state_t::WARNING_MAX_BIT - tion4s_state_t::WARNING_MIN_BIT + 1;
static const char *const WARNINGS[WARNINGS_COUNT] = {
    // WS01
    "Температура поступающего воздуха выше допустимого значения",
    // WS02
    "Температура поступающего воздуха ниже допустимого значения",
    // WS03
    "Температура платы управления выше допустимого значения",
    // WS04
    "Температура силовой платы выше допустимого значения",
    // WS05
    "Температура платы управления ниже допустимого значения",
    // WS06
    "Температура силовой платы ниже допустимого значения",
};

void tion4s_state_t::report_errors(uint32_t errors) {
  tion::enum_errors(errors, tion4s_state_t::ERROR_MIN_BIT, tion4s_state_t::ERROR_MAX_BIT, nullptr,
                    [](uint8_t err, const void *) {
                      if (err > 0 && (err - 1) < ERRORS_COUNT) {
                        TION_REPORT_EC(TAG, err, ERRORS[err - 1]);
                      } else {
                        TION_REPORT_EC_UNK(TAG, err);
                      }
                    });
  tion::enum_errors(errors, tion4s_state_t::WARNING_MIN_BIT, tion4s_state_t::WARNING_MAX_BIT, nullptr,
                    [](uint8_t err, const void *) {
                      if (err > 0 && (err - 1) < WARNINGS_COUNT) {
                        TION_REPORT_WS(TAG, err, WARNINGS[err - 1]);
                      } else {
                        TION_REPORT_WS_UNK(TAG, err);
                      }
                    });
}

uint16_t Tion4sApi::get_state_type() const { return FRAME_TYPE_STATE_RSP; }

void Tion4sApi::read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  // do not use switch statement with non-contiguous values, as this will generate a lookup table with wasted space.
#ifdef TION_ENABLE_HEARTBEAT
  if (frame_type == FRAME_TYPE_HEARTBEAT_RSP) {
    struct RawHeartbeatFrame {
      tion::tion_dev_info_t::work_mode_t work_mode;  // always 1
    } PACKED;
    if (frame_data_size != sizeof(RawHeartbeatFrame)) {
      TION_LOGW(TAG, "Incorrect heartbeat response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawHeartbeatFrame *>(frame_data);
      TION_LOGD(TAG, "Response Heartbeat (%u)", frame->work_mode);
      this->on_heartbeat_fn.call_if(frame->work_mode);
    }
    return;
  }
#endif
  if (frame_type == FRAME_TYPE_STATE_RSP) {
    using RawStateFrame = tion4s_raw_frame_t<tion4s_state_t>;
    if (frame_data_size != sizeof(RawStateFrame)) {
      TION_LOGW(TAG, "Incorrect state response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawStateFrame *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] %s", frame->request_id, frame->request_id == 1 ? "State" : "Write State");
      this->update_state_(frame->data);
      this->notify_state_(frame->request_id);
    }
    return;
  }

  if (frame_type == FRAME_TYPE_TURBO_RSP) {
    using RawTurboFrame = tion4s_raw_frame_t<tion4s_turbo_t>;
    // struct RawTurboFrame {
    //   uint32_t request_id;
    //   tion4s_turbo_t data;
    // } PACKED;
    if (frame_data_size != sizeof(RawTurboFrame)) {
      TION_LOGW(TAG, "Incorrect turbo response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawTurboFrame *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] Turbo", frame->request_id);
      this->update_turbo_(frame->data);
      this->on_turbo.call_if(frame->data, frame->request_id);
    }
    return;
  }

  if (frame_type == FRAME_TYPE_DEV_INFO_RSP) {
    if (frame_data_size != sizeof(tion_dev_info_t)) {
      TION_LOGW(TAG, "Incorrect device info response data size: %zu", frame_data_size);
    } else {
      TION_LOGD(TAG, "Response Device info");
      this->update_dev_info_(*static_cast<const tion_dev_info_t *>(frame_data));
    }
    return;
  }
#ifdef TION_ENABLE_SCHEDULER
  if (frame_type == FRAME_TYPE_TIME_RSP) {
    using RawTimeFrame = tion4s_raw_frame_t<tion4s_time_t>;
    // struct RawTimeFrame {
    //   uint32_t request_id;
    //   tion4s_time_t data;
    // } PACKED;
    if (frame_data_size != sizeof(RawTimeFrame)) {
      TION_LOGW(TAG, "Incorrect time response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawTimeFrame *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] Time", frame->request_id);
      this->on_time.call_if(frame->data.unix_time, frame->request_id);
    }
    return;
  }

  if (frame_type == FRAME_TYPE_TIMER_RSP) {
    using RawTimerFrame = tion4s_raw_frame_t<tion4s_timer_rsp_t>;
    // struct RawTimerFrame {
    //   uint32_t request_id;
    //   uint8_t timer_id;
    //   tion4s_timer_t timer;
    // } PACKED;
    if (frame_data_size != sizeof(RawTimerFrame)) {
      TION_LOGW(TAG, "Incorrect timer response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawTimerFrame *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] Timer %u", frame->request_id, frame->data.timer_id);
      this->on_timer.call_if(frame->data.timer_id, frame->data.timer, frame->request_id);
    }
    return;
  }

  if (frame_type == FRAME_TYPE_TIMERS_STATE_RSP) {
    using RawTimersStateFrame = tion4s_raw_frame_t<tion4s_timers_state_t>;
    // struct RawTimersStateFrame {
    //   uint32_t request_id;
    //   tion4s_timers_state_t data;
    // } PACKED;
    if (frame_data_size != sizeof(RawTimersStateFrame)) {
      TION_LOGW(TAG, "Incorrect timers state response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawTimersStateFrame *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] Timers state", frame->request_id);
      this->on_timers_state.call_if(frame->data, frame->request_id);
    }
    return;
  }
#endif
#ifdef TION_ENABLE_DIAGNOSTIC
  if (frame_type == FRAME_TYPE_ERR_CNT_RSP) {
    using RawErrorFrame = tion4s_raw_frame_t<tion4s_errors_t>;
    // struct RawErrorFrame {
    //   uint32_t request_id;
    //   tion4s_errors_t data;
    // } PACKED;
    if (frame_data_size != sizeof(RawErrorFrame)) {
      TION_LOGW(TAG, "Incorrect error response data size: %zu", frame_data_size);
    } else {
      auto *frame = static_cast<const RawErrorFrame *>(frame_data);
      TION_LOGD(TAG, "Response[%" PRIu32 "] Errors", frame->request_id);
      // this->on_errors(frame->errors, frame->request_id);
    }
    return;
  }

  if (frame_type == FRAME_TYPE_TEST_RSP) {
    struct RawTestFrame {
      uint8_t unknown[440];
    } PACKED;
    if (frame_data_size != sizeof(RawTestFrame)) {
      TION_LOGW(TAG, "Incorrect test response data size: %zu", frame_data_size);
    } else {
      TION_LOGD(TAG, "Response Test");
    }
    return;
  }
#endif
  TION_LOGW(TAG, "Unsupported frame %04X: %s", frame_type, tion::hex_cstr(frame_data, frame_data_size));
}

bool Tion4sApi::request_dev_info_() const {
  TION_LOGD(TAG, "Request Device info");
  return this->write_frame(FRAME_TYPE_DEV_INFO_REQ);
}

bool Tion4sApi::request_state_() const {
  TION_LOGD(TAG, "Request State");
  return this->write_frame(FRAME_TYPE_STATE_REQ);
}

bool Tion4sApi::request_turbo_() const {
  TION_LOGD(TAG, "Request Turbo");
  // TODO проверить, возможно необходимо/можно посылать request_id
  return this->write_frame(FRAME_TYPE_TURBO_REQ);
}

bool Tion4sApi::write_state(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Write state", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tion4s_raw_state_set_req_t req(request_id, state);
  TION_DUMP(TAG, "req  : %" PRIu32, req.request_id);
  TION_DUMP(TAG, "power: %s", ONOFF(req.data.power_state));
  TION_DUMP(TAG, "sound: %s", ONOFF(req.data.sound_state));
  TION_DUMP(TAG, "led  : %s", ONOFF(req.data.led_state));
  TION_DUMP(TAG, "heat : %s", ONOFF(req.data.heater_mode != tion4s_state_t::HEATER_MODE_FANONLY));
  TION_DUMP(TAG, "comm : %s", req.data.comm_source == tion::CommSource::AUTO ? "AUTO" : "USER");
  TION_DUMP(TAG, "auto : %s", ONOFF(req.data.ma_connected));
  TION_DUMP(TAG, "gate : %s",
            req.data.gate_position == tion4s_state_t::GATE_POSITION_OUTDOOR ? "inflow" : "recirculation");
  TION_DUMP(TAG, "temp : %u", req.data.target_temperature);
  TION_DUMP(TAG, "fan  : %u", req.data.fan_speed);
  return this->write_frame(FRAME_TYPE_STATE_SET, req);
}

bool Tion4sApi::reset_filter(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Reset filter", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tion4s_raw_state_set_req_t req(request_id, state);
  req.data.filter_reset = true;
  req.data.filter_time = 0;
  return this->write_frame(FRAME_TYPE_STATE_SET, req);
}

bool Tion4sApi::factory_reset(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Factory reset", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tion4s_raw_state_set_req_t req(request_id, state);
  req.data.factory_reset = true;
  return this->write_frame(FRAME_TYPE_STATE_SET, req);
}

bool Tion4sApi::set_turbo(uint16_t time, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Turbo %u", request_id, time);
  const tion4s_raw_frame_t<tion4s_turbo_set_t> req{.request_id = request_id, .data = {.time = time, .err_code = 0}};
  return this->write_frame(FRAME_TYPE_TURBO_SET, req);
};

#ifdef TION_ENABLE_HEARTBEAT
bool Tion4sApi::send_heartbeat() const {
  TION_LOGD(TAG, "Request Heartbeat");
  return this->write_frame(FRAME_TYPE_HEARTBEAT_REQ);
}
#endif

#ifdef TION_ENABLE_SCHEDULER
bool Tion4sApi::request_time(uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Time", request_id);
  const struct {
    uint32_t request_id;
  } PACKED req{.request_id = request_id};
  return this->write_frame(FRAME_TYPE_TIME_REQ, req);
}

bool Tion4sApi::request_timer(uint8_t timer_id, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Timer %u", request_id, timer_id);
  const tion4s_raw_frame_t<tion4s_timer_req_t> req{.request_id = request_id, .data = {.timer_id = timer_id}};
  return this->write_frame(FRAME_TYPE_TIMER_REQ, req);
}

bool Tion4sApi::request_timers(uint32_t request_id) const {
  bool res = true;
  for (uint8_t timer_id = 0; timer_id < tion4s_timers_state_t::TIMERS_COUNT; timer_id++) {
    res &= this->request_timer(timer_id, request_id);
  }
  return res;
}

bool Tion4sApi::write_timer(uint8_t timer_id, const tion4s_timer_t &timer, uint32_t request_id) const {
  const struct {
    uint32_t request_id;
    uint8_t timer_id;
    tion4s_timer_t timer;
  } PACKED req{.request_id = request_id, .timer_id = timer_id, .timer = timer};
  return this->write_frame(FRAME_TYPE_TIMER_SET, req);
}

bool Tion4sApi::request_timers_state(const uint32_t request_id) const {
  const struct {
    uint32_t request_id;
  } PACKED req{.request_id = request_id};
  return this->write_frame(FRAME_TYPE_TIMERS_STATE_REQ, req);
}

bool Tion4sApi::set_time(time_t time, uint32_t request_id) const {
  const tion4s_raw_frame_t<tion4s_time_t> req{.request_id = request_id, .data = {.unix_time = time}};
  TION_LOGD(TAG, "Request[%" PRIu32 "] Time %lld", request_id, req.data.unix_time);
  return this->write_frame(FRAME_TYPE_TIME_SET, req);
}
#endif
#ifdef TION_ENABLE_DIAGNOSTIC
bool Tion4sApi::request_errors() const {
  TION_LOGD(TAG, "Request Errors");
  return this->write_frame(FRAME_TYPE_ERR_CNT_REQ);
}

bool Tion4sApi::request_test() const {
  TION_LOGD(TAG, "Request Test");
  return this->write_frame(FRAME_TYPE_TEST_REQ);
}
#endif

bool Tion4sApi::reset_errors(const TionState &state, uint32_t request_id) const {
  TION_LOGD(TAG, "Request[%" PRIu32 "] Errors reset", request_id);
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tion4s_raw_state_set_req_t req(request_id, state);
  req.data.error_reset = true;
  return this->write_frame(FRAME_TYPE_STATE_SET, req);
}

void Tion4sApi::request_state() {
  if (this->state_.firmware_version == 0) {
    this->request_dev_info_();
  }
  if (this->traits_.supports_boost) {
    this->request_turbo_();
  }
  this->request_state_();
}

Tion4sApi::Tion4sApi() {
  this->traits_.errors_decode = tion4s_state_t::decode_errors;
  this->traits_.errors_report = tion4s_state_t::report_errors;

  this->traits_.supports_heater_var = true;
  this->traits_.supports_work_time = true;
  this->traits_.supports_airflow_counter = true;
  this->traits_.supports_fan_time = true;
  this->traits_.supports_led_state = true;
  this->traits_.supports_sound_state = true;
  this->traits_.supports_pcb_ctl_temperature = true;
  this->traits_.supports_pcb_pwr_temperature = true;
  this->traits_.supports_gate_position_change = true;
  this->traits_.supports_gate_error = true;
  this->traits_.supports_reset_filter = true;
  this->traits_.max_heater_power = TION_4S_HEATER_POWER1;
  this->traits_.max_fan_speed = 6;
  this->traits_.min_target_temperature = TION_MIN_TEMPERATURE;
  this->traits_.max_target_temperature = TION_MAX_TEMPERATURE;

  this->traits_.max_fan_power[0] = TION_4S_MAX_FAN_POWER0;
  this->traits_.max_fan_power[1] = TION_4S_MAX_FAN_POWER1;
  this->traits_.max_fan_power[2] = TION_4S_MAX_FAN_POWER2;
  this->traits_.max_fan_power[3] = TION_4S_MAX_FAN_POWER3;
  this->traits_.max_fan_power[4] = TION_4S_MAX_FAN_POWER4;
  this->traits_.max_fan_power[5] = TION_4S_MAX_FAN_POWER5;
  this->traits_.max_fan_power[6] = TION_4S_MAX_FAN_POWER6;

  this->traits_.auto_prod = PROD;
}

void Tion4sApi::enable_native_boost_support() { this->traits_.supports_boost = true; }

void Tion4sApi::update_dev_info_(const tion::tion_dev_info_t &dev_info) {
  this->state_.firmware_version = dev_info.firmware_version;
  this->state_.hardware_version = dev_info.hardware_version;
}

void Tion4sApi::update_state_(const tion4s_state_t &state) {
  this->state_.initialized = true;

  this->state_.power_state = state.power_state;
  this->state_.heater_state = state.heater_mode == tion4s_state_t::HEATER_MODE_HEATING;
  this->state_.sound_state = state.sound_state;
  this->state_.led_state = state.led_state;
  this->state_.comm_source = state.comm_source;
  this->state_.auto_state = state.ma_connected;
  this->state_.filter_state = state.filter_state;
  this->state_.gate_error_state = (state.errors & tion4s_state_t::GATE_ERROR_BIT) != 0;
  this->state_.gate_position =                                           //-//
      state.gate_position == tion4s_state_t::GATE_POSITION_OUTDOOR       //-//
          ? TionGatePosition::OUTDOOR                                    //-//
          : state.gate_position == tion4s_state_t::GATE_POSITION_INDOOR  //-//
                ? TionGatePosition::INDOOR                               //-//
                : TionGatePosition::UNKNOWN;                             //-//
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
  this->traits_.max_heater_power =                                        //-//
      state.heater_present == tion4s_state_t::HEATER_PRESENT_1000W        //-//
          ? TION_4S_HEATER_POWER1                                         //-//
          : state.heater_present == tion4s_state_t::HEATER_PRESENT_1400W  //-//
                ? TION_4S_HEATER_POWER2                                   //-//
                : 0;                                                      //-//
  this->traits_.max_fan_speed = state.max_fan_speed;
  // this->traits_.min_target_temperature = -30;
  // this->traits_.min_target_temperature = 25;
  // this->state_.hardware_version = dev_info.hardware_version;
  // this->state_.firmware_version = dev_info.firmware_version;
  this->state_.pcb_ctl_temperature = state.pcb_ctl_temperature;
  this->state_.pcb_pwr_temperature = state.pcb_pwr_temperature;
  this->state_.errors = state.errors;

  this->dump_state_(state);
}

void Tion4sApi::dump_state_(const tion4s_state_t &state) const {
  this->state_.dump(TAG, this->traits_);
  TION_DUMP(TAG, "heater_mode : %s (%u)",
            state.heater_mode == tion4s_state_t::HEATER_MODE_HEATING   ? "heating"
            : state.heater_mode == tion4s_state_t::HEATER_MODE_FANONLY ? "fanonly"
                                                                       : "unknown",
            state.heater_mode);
  TION_DUMP(TAG, "heater_state: %s", ONOFF(state.heater_state));
  TION_DUMP(TAG, "heater_prsnt: %u", state.heater_present);
  TION_DUMP(TAG, "active_timer: %s", ONOFF(state.active_timer));
  TION_DUMP(TAG, "ma_auto     : %s", ONOFF(state.ma_auto));
  TION_DUMP(TAG, "ma_connected: %s", ONOFF(state.ma_connected));
  TION_DUMP(TAG, "airflow_cnt : %" PRIu32, state.counters.airflow_counter);
  TION_DUMP(TAG, "reserved    : 0x%02X (%s)", state.reserved, tion::get_flag_bits(state.reserved));
}

void Tion4sApi::update_turbo_(const tion4s_turbo_t &turbo) {
  this->state_.boost_time_left = turbo.is_active ? turbo.turbo_time : 0;
}

void Tion4sApi::boost_enable_native_(bool state) {
  if (!this->traits_.supports_boost) {
    TION_LOGW(TAG, "Native boost is unsupported");
    return;
  }
  TION_LOGD(TAG, "Enable native boost: %s", ONOFF(state));
  this->set_turbo(this->traits_.boost_time, ++this->request_id_);
}

}  // namespace tion_4s
}  // namespace dentra
