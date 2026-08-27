#include <cstring>
#include <cinttypes>
#include <cstdlib>

#include "log.h"
#include "utils.h"
#include "tion-api-3s.h"
#include "tion-api-defines.h"

namespace dentra {
namespace tion {

static const char *const TAG = "tion-api-3s";

}
}  // namespace dentra

namespace dentra {
namespace tion_3s {

using tion::TionTraits;

constexpr size_t ERRORS_COUNT = 17;

static const char *const ERRORS[ERRORS_COUNT] = {
    // EC01
    "Температура воздуха на входе в устройство выше максимально допустимой",
    // EC02
    "Температура воздуха на входе в устройство ниже минимально допустимой",
    // EC03
    "Температура воздуха на выходе из устройства выше максимально допустимой",
    // EC04
    "Нагреватель не обеспечивает подогрев воздуха до 0 °C",
    // EC05
    "Заслонка не перешла ни в одно из крайних положений",
    // EC06
    "Переохлаждение платы управления",
    // EC07
    "Неисправность в цепи одного из датчиков температуры выходящего воздуха",
    // EC08
    "Неисправность в цепи датчика температуры входящего воздуха",
    // EC09
    "Неисправность в цепи одного из датчиков температуры выходящего воздуха",
    // EC10
    "Неисправность в цепи датчика температуры входящего воздуха",
    // EC11
    "Нарушение связи между платой силовой и платой управления",
    // EC12
    "Блок заслонки из режима \"Рециркуляция\" не перешел в режим \"Приток\"",
    // EC13
    "Блок заслонки из режима \"Приток\" не перешел в режим \"Рециркуляция\"",
    // EC14
    "Переохлаждение платы силовой",
    // EC15
    "Перегрев платы силовой",
    // EC16
    "Обрыв в цепи питания датчика выходного (верхнего) датчика температуры",
    // EC17
    "Замыкание в цепи датчика выходного (верхнего) датчика температуры",
};

std::string tion3s_state_t::decode_errors(uint32_t errors) {
  if (errors == 0) {
    return {};
  }

  return "EC" + std::to_string(errors);
}

void tion3s_state_t::report_errors(uint32_t errors) {
  if (errors > 0) {
    uint8_t err = static_cast<uint8_t>(errors);
    if (errors < ERRORS_COUNT) {
      TION_REPORT_EC(tion::TAG, static_cast<int>(err), ERRORS[err - 1]);
    } else {
      TION_REPORT_EC_UNK(tion::TAG, static_cast<int>(err));
    }
  }
}

}  // namespace tion_3s
}  // namespace dentra

namespace dentra {
namespace tion {

using namespace tion_3s;

static const uint8_t PROD[] = {0, TION_3S_AUTO_PROD};

struct Tion3sTimersResponse {
  struct {
    uint8_t hours;
    uint8_t minutes;
  } timers[4];
};

uint16_t Tion3sApi::get_state_type() const { return FRAME_TYPE_RSP(FRAME_TYPE_STATE_GET); }

void Tion3sApi::read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  // invalid size is never possible
  // if (frame_data_size != sizeof(tion3s_state_t)) {
  //   TION_LOGW(TAG, "Incorrect state data size: %zu", frame_data_size);
  //   return;
  // }
  if (frame_type == FRAME_TYPE_RSP(FRAME_TYPE_STATE_GET)) {
    TION_LOGD(TAG, "Response State Get");
    this->update_state_(*static_cast<const tion3s_state_t *>(frame_data));
    this->notify_state_(0);
  } else if (frame_type == FRAME_TYPE_RSP(FRAME_TYPE_STATE_SET)) {
    TION_LOGD(TAG, "Response State Set");
    this->update_state_(*static_cast<const tion3s_state_t *>(frame_data));
    this->notify_state_(0);
  } else if (frame_type == FRAME_TYPE_RSP(FRAME_TYPE_TIMERS_GET)) {
    TION_LOGD(TAG, "Response Timers: %s", hex_cstr(frame_data, frame_data_size));
    // структура Tion3sTimersResponse
  } else if (frame_type == FRAME_TYPE_RSP(FRAME_TYPE_SRV_MODE_SET)) {
    // есть подозрение, что актуальными является первые два байта,
    // остальное условный мусор из предыдущей команды
    //
    // один из ответов на команду сопряжения через удержание кнопки на бризере
    // B3.50.01.00.08.00.08.00.08.00.00.00.00.00.00.00.00.00.00.5A
    // еще:
    // [17:36:21][V][vport:015]: VTX: 3D.01
    // [17:36:21][V][vport:011]: VRX: B3.10.21.19.02.00.19.19.17.68.01.0F.04.00.1E.00.00.3C.00 (19)
    // [17:37:16][V][vport:015]: VTX: 3D.04
    // [17:37:16][V][vport:011]: VRX: B3.40.11.00.08.00.08.00.08.00.00.00.00.00.00.00.00.00.00 (19)
    // [17:37:21][V][vport:015]: VTX: 3D.01
    // [17:37:21][V][vport:011]: VRX: B3.10.21.19.02.00.19.19.17.68.01.0F.05.00.1E.00.00.3C.00 (19)
    // [17:37:39][V][vport:011]: VRX: B3.50.01.00.02.00.19.19.17.68.01.0F.05.00.1E.00.00.3C.00 (19)
    // [17:38:09][V][vport:011]: VRX: B3.50.00.00.02.00.19.19.17.68.01.0F.05.00.1E.00.00.3C.00 (19)
    // [17:38:16][V][vport:015]: VTX: 3D.04
    // [17:38:16][V][vport:011]: VRX: B3.40.11.00.08.00.08.00.08.00.00.00.00.00.00.00.00.00.00 (19)
    // [17:38:21][V][vport:015]: VTX: 3D.01
    // [17:38:21][V][vport:011]: VRX: B3.10.21.19.02.00.19.19.17.68.01.0F.06.00.1E.00.00.3C.00 (19)
    TION_LOGD(TAG, "Response Pair: %s", hex_cstr(frame_data, frame_data_size));
  } else {
    TION_LOGW(TAG, "Unsupported frame %04X: %s", frame_type, hex_cstr(frame_data, frame_data_size));
  }
}

bool Tion3sApi::pair() const {
  TION_LOGD(TAG, "Request Pair");
  const struct {
    uint8_t pair;
  } PACKED pair{.pair = 1};
  return this->write_frame(FRAME_TYPE_REQ(FRAME_TYPE_SRV_MODE_SET), pair);
}

bool Tion3sApi::request_state_() const {
  TION_LOGD(TAG, "Request State Get");
  return this->write_frame(FRAME_TYPE_REQ(FRAME_TYPE_STATE_GET));
}

bool Tion3sApi::write_state_(const tion::TionState &state) const {
  TION_LOGD(TAG, "Request State Set");
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tion3s_state_set_t st_set(state);
  TION_DUMP(TAG, "fan   : %u", st_set.fan_speed);
  TION_DUMP(TAG, "temp  : %u", st_set.target_temperature);
  TION_DUMP(TAG, "gate  : %s",
            st_set.gate_position == tion3s_state_t::GATE_POSITION_INDOOR    ? "indoor"
            : st_set.gate_position == tion3s_state_t::GATE_POSITION_OUTDOOR ? "outdoor"
            : st_set.gate_position == tion3s_state_t::GATE_POSITION_MIXED   ? "mixed"
                                                                            : "unknown");
  TION_DUMP(TAG, "heat  : %s", ONOFF(st_set.flags.heater_state));
  TION_DUMP(TAG, "power : %s", ONOFF(st_set.flags.power_state));
  TION_DUMP(TAG, "sound : %s", ONOFF(st_set.flags.sound_state));
  TION_DUMP(TAG, "auto  : %s", ONOFF(st_set.flags.ma_auto));
  TION_DUMP(TAG, "ma    : %s", ONOFF(st_set.flags.ma_connected));
  TION_DUMP(TAG, "preset: %s", ONOFF(st_set.flags.preset_state));

  return this->write_frame(FRAME_TYPE_REQ(FRAME_TYPE_STATE_SET), st_set);
}

bool Tion3sApi::reset_filter_(const tion::TionState &state) const {
  TION_LOGD(TAG, "Request Filter Time Reset");
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }

  // предположительно сброс ресурса фильтра выполняется командой 2
  // 3D:01:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:01:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:02:01:17:02:0A:01:02:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:01:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:04:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:04:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:04:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A

  // еще пример
  // 3D:02:01:17:02:0A:01:02:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:01:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A
  // 3D:04:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:5A

  tion3s_state_set_t st_set(state);
  st_set.filter_time.reset = true;
  return this->write_frame(FRAME_TYPE_REQ(FRAME_TYPE_STATE_SET), st_set);
}

bool Tion3sApi::request_command4() const {
  TION_LOGD(TAG, "Request Timers");
  return this->write_frame(FRAME_TYPE_REQ(FRAME_TYPE_TIMERS_GET));
}

bool Tion3sApi::factory_reset_(const tion::TionState &state) const {
  TION_LOGD(TAG, "Request Factory Reset");
  if (!state.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized");
    return false;
  }
  tion3s_state_set_t st_set(state);
  st_set.factory_reset = true;
  return this->write_frame(FRAME_TYPE_REQ(FRAME_TYPE_STATE_SET), st_set);
}

Tion3sApi::Tion3sApi() {
  this->traits_.errors_decode = tion3s_state_t::decode_errors;
  this->traits_.errors_report = tion3s_state_t::report_errors;

  this->traits_.supports_sound_state = true;
  this->traits_.supports_gate_position_change = true;
  this->traits_.supports_gate_position_change_mixed = true;
#ifdef TION_ENABLE_ANTIFREEZE
  this->traits_.supports_manual_antifreeze = true;
#endif
  this->traits_.supports_reset_filter = true;
  this->traits_.max_heater_power = TION_3S_HEATER_POWER;
  this->traits_.max_fan_speed = 6;
  this->traits_.min_target_temperature = TION_MIN_TEMPERATURE;
  this->traits_.max_target_temperature = TION_MAX_TEMPERATURE;

  this->traits_.max_fan_power[0] = TION_3S_MAX_FAN_POWER0;
  this->traits_.max_fan_power[1] = TION_3S_MAX_FAN_POWER1;
  this->traits_.max_fan_power[2] = TION_3S_MAX_FAN_POWER2;
  this->traits_.max_fan_power[3] = TION_3S_MAX_FAN_POWER3;
  this->traits_.max_fan_power[4] = TION_3S_MAX_FAN_POWER4;
  this->traits_.max_fan_power[5] = TION_3S_MAX_FAN_POWER5;
  this->traits_.max_fan_power[6] = TION_3S_MAX_FAN_POWER6;

  this->traits_.auto_prod = PROD;
}

void Tion3sApi::update_state_(const tion_3s::tion3s_state_t &state) {
  this->state_.initialized = true;

  this->state_.power_state = state.flags.power_state;
  this->state_.heater_state = state.flags.heater_state;
  this->state_.sound_state = state.flags.sound_state;
  // this->state_.led_state = state.led_state;
  // this->state_.comm_source = state.comm_source;
  this->state_.auto_state = state.flags.ma_connected;
  this->state_.filter_state = state.filter_time <= 30;
  this->state_.gate_error_state = state.last_error == tion_3s::tion3s_state_t::GATE_ERROR_NUM;
  this->state_.gate_position =                                                  //-//
      state.gate_position == tion3s_state_t::GATE_POSITION_INDOOR               //-//
          ? TionGatePosition::INDOOR                                            //-//
          : state.gate_position == tion3s_state_t::GATE_POSITION_MIXED          //-//
                ? TionGatePosition::MIXED                                       //-//
                : state.gate_position == tion3s_state_t::GATE_POSITION_OUTDOOR  //-//
                      ? TionGatePosition::OUTDOOR                               //-//
                      : TionGatePosition::UNKNOWN;                              //-//

  this->state_.fan_speed = state.fan_speed;
  this->state_.outdoor_temperature = state.outdoor_temperature;
  this->state_.current_temperature = state.current_temperature();
  this->state_.target_temperature = state.target_temperature;
  this->state_.productivity = state.productivity;
  // this->state_.heater_var = state.heater_var;
  this->state_.work_time = tion::millis() / 1000;
  // this->state_.fan_time = state.counters.fan_time;
  this->state_.filter_time_left = uint32_t(state.filter_time > 360 ? 1 : state.filter_time) * (24 * 3600);
  // this->state_.airflow_counter = state.counters.airflow_counter;
  // this->traits_.heater_present = TION_3S_HEATER_POWER;
  // this->traits_.max_fan_speed = state.max_fan_speed;
  // this->traits_.min_target_temperature = -30;
  // this->traits_.min_target_temperature = 25;
  // this->state_.hardware_version=dev_info.hardware_version;
  this->state_.firmware_version = state.firmware_version;
  // this->state_.pcb_ctl_temperature = state.pcb_ctl_temperature;
  // this->state_.pcb_pwr_temperature = state.pcb_pwr_temperature;
  this->state_.errors = state.last_error;

  this->dump_state_(state);
}

void Tion3sApi::dump_state_(const tion_3s::tion3s_state_t &state) const {
  this->state_.dump(TAG, this->traits_);
  TION_DUMP(TAG, "filter_days : %u d", state.filter_days);
  TION_DUMP(TAG, "current_T1  : %d °C", state.current_temperature1);
  TION_DUMP(TAG, "current_T2  : %d °C", state.current_temperature2);
  TION_DUMP(TAG, "timer_state : %s", ONOFF(state.flags.timer_state));
  TION_DUMP(TAG, "preset_state: %s", ONOFF(state.flags.preset_state));
  TION_DUMP(TAG, "save        : %s", ONOFF(state.flags.save));
  TION_DUMP(TAG, "ma_auto     : %s", ONOFF(state.flags.ma_auto));
  TION_DUMP(TAG, "ma_connected: %s", ONOFF(state.flags.ma_connected));
  TION_DUMP(TAG, "ma_pairing  : %s", ONOFF(state.flags.ma_pairing));
  TION_DUMP(TAG, "hours       : %u h", state.hours);
  TION_DUMP(TAG, "minutes     : %u min", state.minutes);
  TION_DUMP(TAG, "reserved    : 0x%02X (%s)", state.flags.reserved, tion::get_flag_bits(state.flags.reserved));
}

}  // namespace tion
}  // namespace dentra
