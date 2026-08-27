#pragma once

#include <cstdint>
#include "tion-api-internal.h"

namespace dentra {
namespace tion_lt {

enum {
  FRAME_TYPE_STATE_SET = 0x1230,  // set no save req
  FRAME_TYPE_STATE_RSP = 0x1231,
  FRAME_TYPE_STATE_REQ = 0x1232,
  FRAME_TYPE_STATE_SAV = 0x1234,  // set save req

  FRAME_TYPE_DEV_INFO_REQ = 0x4009,
  FRAME_TYPE_DEV_INFO_RSP = 0x400A,

  // не существует
  FRAME_TYPE_AUTOKIV_PARAM_SET = 0x1240,
  // не существует
  FRAME_TYPE_AUTOKIV_PARAM_RSP = 0x1241,
  // не существует
  FRAME_TYPE_AUTOKIV_PARAM_REQ = 0x1242,

  FRAME_TYPE_TEST_REQ = 0x1111,
  FRAME_TYPE_TEST_RSP = 0x2222,  // returns 0x400 bytes
};

#pragma pack(push, 1)

using tion_lt_state_counters_t = tion::tion_state_counters_t<10>;

// NOLINTNEXTLINE(readability-identifier-naming)
struct button_presets_t {
  enum { PRESET_NUMBER = 3 };
  /// Целевая температура.
  int8_t tmp[PRESET_NUMBER];

  /// Скорость вентиляции.
  uint8_t fan[PRESET_NUMBER];
};

// NOLINTNEXTLINE(readability-identifier-naming)
struct tionlt_state_t {
  enum {
    ERROR_MIN_BIT = 0,
    ERROR_MAX_BIT = 10,
    WARNING_MIN_BIT = 24,
    WARNING_MAX_BIT = 27,
    GATE_ERROR_BIT = (1 << 0) | (1 << 1) | (1 << 2),
  };

  enum GateState : uint8_t {
    // закрыто
    CLOSED = 1,
    // открыто
    OPENED = 2,
  };

  // Байт 0-1.
  struct {
    // Байт 0, бит 0. Состояние бризера
    bool power_state : 1;
    // Байт 0, бит 1. Состояние звуковых оповещений
    bool sound_state : 1;
    // Байт 0, бит 2. Состояние световых оповещений
    bool led_state : 1;
    // Байт 0, бит 3.
    tion::CommSource comm_source : 1;
    // Байт 0, бит 4. Предупреждение о необходимости замены фильтра.
    bool filter_state : 1;
    // Байт 0, бит 5.
    bool ma_auto : 1;
    // Байт 0, бит 6.
    bool heater_state : 1;
    // Байт 0, бит 7.
    bool heater_present : 1;
    // Байт 1, бит 0. the presence of the KIV mode
    bool kiv_present : 1;
    // Байт 1, бит 1. state of the KIV mode
    bool kiv_active : 1;
    // reserved
    uint8_t reserved : 6;
  };
  GateState gate_state;
  // Байт 3. Настроенная температура подогрева.
  int8_t target_temperature;
  // Байт 4. Скорость вентиляции.
  uint8_t fan_speed;
  // Байт 5. Температура воздуха на входе в бризер (температура на улице).
  int8_t outdoor_temperature;
  // Байт 6. Текущая температура воздуха после нагревателя (внутри помещения).
  int8_t current_temperature;
  // Байт 7. Внутренняя температура платы управления.
  int8_t pcb_temperature;
  // Байт 8-23. 8-11 - work_time, 12-15 - fan_time, 16-19 - filter_time, 20-23 - airflow_counter
  tion_lt_state_counters_t counters;
  // Байт 24-27.
  uint32_t errors;
  // Байт 28-47.
  struct {
    enum { ERROR_TYPE_NUMBER = 20 };
    uint8_t er[ERROR_TYPE_NUMBER];
  } errors_cnt;
  // Байт 48-53.
  button_presets_t button_presets;
  // Байт 54.
  uint8_t max_fan_speed;
  // Байт 55.
  uint8_t heater_var;
  // Байт 56.
  uint8_t test_type;

  static std::string decode_errors(uint32_t errors) {
    return tion::decode_errors(errors, ERROR_MIN_BIT, ERROR_MAX_BIT, WARNING_MIN_BIT, WARNING_MAX_BIT);
  }
  static void report_errors(uint32_t errors);
};

struct tionlt_state_get_req_t {
  uint32_t request_id;
  tionlt_state_t state;
};

// used to change state of device
// NOLINTNEXTLINE(readability-identifier-naming)
struct _tionlt_state_set_t {
  struct {
    // Байт 0, бит 0
    bool power_state : 1;
    // Байт 0, бит 1
    bool sound_state : 1;
    // Байт 0, бит 2
    bool led_state : 1;
    // Байт 0, бит 3
    bool ma_auto : 1;
    // Байт 0, бит 4
    bool heater_state : 1;
    // Байт 0, бит 5
    tion::CommSource comm_source : 1;  // last_com_source или save
    // Байт 0, бит 6
    bool factory_reset : 1;
    // Байт 0, бит 7
    bool error_reset : 1;
    // Байт 1, бит 0
    bool filter_reset : 1;
    // uint8_t save;
    uint8_t reserved : 7;
  };
  // Байт 2. Состояние затворки.
  tionlt_state_t::GateState gate_state;
  // Байт 3.
  int8_t target_temperature;
  // Байт 4. Скорость вентиляции.
  uint8_t fan_speed;
  // Байт 5-10. Пресеты кнопок.
  button_presets_t button_presets;
  // Байт 11-12. Количество __дней__ для сброса ресурса фильтра.
  uint16_t filter_time;
  uint8_t test_type;

  _tionlt_state_set_t() = delete;
  _tionlt_state_set_t(const tion::TionState &state, const button_presets_t &btn_presets)
      : power_state(state.power_state),
        sound_state(state.sound_state),
        led_state(state.led_state),
        ma_auto(state.auto_state),
        heater_state(state.heater_state),
        // в Tion Remote этот бит не выставляется, возможно он инвертирован
        comm_source(tion::CommSource::AUTO),
        factory_reset(false),
        error_reset(false),
        filter_reset(false),
        reserved(0),
        // FIXME корректируем позицию заслонки.
        // !!! Lite ONLY !!!
        // Проверить, можем ли мы открыть заслонку при выключенном бризере и вообще управлять ей.
        // В Tion Remote выставляется так:
        // gate_pos = (fan_speed > 0 || target_temperature > 0) ? OPENED : CLOSED;
        // но с учетом того что в Tion Remote fan_speed всегда > 0, то вообще всегда OPENED
        gate_state(tionlt_state_t::GateState::OPENED),
        // gate_state(state.gate_position == tion::TionGatePosition::OPENED ? tionlt_state_t::GateState::OPENED :
        // tionlt_state_t::GateState::CLOSED),
        target_temperature(state.target_temperature),
        fan_speed(state.fan_speed),
        button_presets(btn_presets),
        filter_time(0),
        test_type(0) {}
};

struct tionlt_state_set_req_t {
  uint32_t request_id;
  _tionlt_state_set_t data;
  tionlt_state_set_req_t(const tion::TionState &state, const button_presets_t &button_presets, uint32_t req_id)
      : request_id(req_id), data(state, button_presets) {}
};

#pragma pack(pop)

}  // namespace tion_lt
}  // namespace dentra
