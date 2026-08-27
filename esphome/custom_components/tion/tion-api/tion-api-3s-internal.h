#pragma once

#include <cstdint>
#include "tion-api-internal.h"

namespace dentra {
namespace tion_3s {

#define FRAME_TYPE(typ, cmd) (((cmd) << 8) | ((typ) & 0xFF))
#define FRAME_TYPE_REQ(cmd) FRAME_TYPE(FRAME_MAGIC_REQ, cmd)
#define FRAME_TYPE_RSP(cmd) FRAME_TYPE(FRAME_MAGIC_RSP, ((cmd) << 4))

enum : uint8_t {
  // request state
  FRAME_TYPE_STATE_GET = 0x1,
  // write state
  FRAME_TYPE_STATE_SET = 0x2,
  // set time
  FRAME_TYPE_TIME_SET = 0x3,
  // timers get and set
  FRAME_TYPE_TIMERS_GET = 0x4,
  // send sevice mode flags
  FRAME_TYPE_SRV_MODE_SET = 0x5,
  FRAME_TYPE_HARD_RESET = 0x6,
  FRAME_TYPE_MA_PAIRING = 0x7,
  // unknown
  FRAME_TYPE_UNKNOWN_8 = 0x8,
  // get alarm
  FRAME_TYPE_ALARM = 0x9,
  // set alrm to on
  FRAME_TYPE_ALARM_ON = 0xA,
  // set alrm to off
  FRAME_TYPE_ALARM_OFF = 0xB,
};

#pragma pack(push, 1)

enum : uint8_t {
  FRAME_MAGIC_REQ = 0x3D,
  FRAME_MAGIC_RSP = 0xB3,
  FRAME_MAGIC_END = 0x5A,
};

// NOLINTNEXTLINE(readability-identifier-naming)
struct tion3s_state_t {
  enum GatePosition : uint8_t { GATE_POSITION_INDOOR = 0, GATE_POSITION_MIXED = 1, GATE_POSITION_OUTDOOR = 2 };
  // Байт 0, бит 0-3. Скорость вентиляции.
  uint8_t fan_speed : 4;
  // Байт 0, бит 4-7. Позиция заслонки.
  GatePosition gate_position : 4;
  // Байт 1. Настроенная температура подогрева.
  int8_t target_temperature;
  // Байт 2-3. Флаги.
  struct Flags {
    // Байт 2, бит 0. Включен режим подогрева.
    bool heater_state : 1;
    // Байт 2, бит 1. Включен бризер.
    bool power_state : 1;
    // Байт 2, бит 2. Включен таймер.
    bool timer_state : 1;
    // Байт 2, бит 3. Включены звуковые оповещения.
    bool sound_state : 1;
    // Байт 2, бит 4.
    bool ma_auto : 1;
    // Байт 2, бит 5. Состояния подключения MagicAir.
    bool ma_connected : 1;
    // Байт 2, бит 6.
    bool save : 1;
    // Байт 2, бит 7.
    bool ma_pairing : 1;
    // Байт 3, бит 0. Возможно это comm_source т.к. в Tion Remote всегда ставиться в 1.
    // В Tion Remote для get_state это presets_state
    bool preset_state : 1;
    // Байт 3, бит 1.
    bool presets_state : 1;
    // зарезервировано
    uint8_t reserved : 6;
  } flags;
  // Байт 4.
  int8_t current_temperature1;
  // Байт 5. Текущая температура воздуха после нагревателя (внутри помещения).
  int8_t current_temperature2;
  // Байт 6. Температура воздуха на входе в бризер (температура на улице).
  int8_t outdoor_temperature;
  // Байт 7-8. Остаточный ресурс фильтров в днях. То, что показывается в приложении как "время жизни фильтров".
  uint16_t filter_time;
  // Байт 9. Часы.
  uint8_t hours;
  // Байт 10. Минуты.
  uint8_t minutes;
  // Байт 11. Код последней ошибки. Выводиться в формате "EC%u".
  uint8_t last_error;
  // Байт 12. Текущая производительность бризера в кубометрах в час.
  uint8_t productivity;
  // Байт 13. Сколько дней прошло с момента установки новых фильтров.
  uint16_t filter_days;
  // Байт 15-16. Текущая версия прошивки.
  uint16_t firmware_version;

  int current_temperature() const {
    // Исходная формула:
    // ((bArr[4] <= 0 ? bArr[5] : bArr[4]) + (bArr[5] <= 0 ? bArr[4] : bArr[5])) / 2;
    auto barr_4 = this->current_temperature1;
    auto barr_5 = this->current_temperature2;
    return ((barr_4 <= 0 ? barr_5 : barr_4) + (barr_5 <= 0 ? barr_4 : barr_5)) / 2;
  }

  enum { GATE_ERROR_NUM = 5 };
  static std::string decode_errors(uint32_t errors);
  static void report_errors(uint32_t errors);
};

// NOLINTNEXTLINE(readability-identifier-naming)
struct tion3s_frame_t {
  enum {
    FRAME_DATA_SIZE = 17,
  };
  uint16_t type;
  uint8_t data[FRAME_DATA_SIZE];
  uint8_t magic;
};

// NOLINTNEXTLINE(readability-identifier-naming)
struct tion3s_state_set_t {
  // Байт 0. Скорость вентиляции.
  uint8_t fan_speed;
  // Байт 1. Целевая температура нагрева.
  int8_t target_temperature;
  // Байт 2. Состояние затворки.
  tion3s_state_t::GatePosition gate_position;
  // Байт 3-4. Флаги.
  tion3s_state_t::Flags flags;
  // Байт 5-7. Управление фильтрами.
  struct {
    bool save : 1;
    bool reset : 1;
    uint8_t reserved : 6;
    uint16_t value;
  } filter_time;
  // Байт 8. Сброс до заводских настроек.
  uint8_t factory_reset;
  // Байт 9. Перевод в сервисный режим.
  uint8_t service_mode;
  // uint8_t reserved[7];

  tion3s_state_set_t() = delete;
  //        0  1  2  3  4  5  6  7  8  9
  // 3D:02 01 17 02 0A.01 02.00.00 00 00 00:00:00:00:00:00:00:5A
  tion3s_state_set_t(const tion::TionState &state)
      : fan_speed(state.fan_speed),
        target_temperature(state.target_temperature),
        gate_position(state.gate_position == tion::TionGatePosition::INDOOR       //-//
                          ? tion3s_state_t::GATE_POSITION_INDOOR                  //-//
                          : state.gate_position == tion::TionGatePosition::MIXED  //-//
                                ? tion3s_state_t::GATE_POSITION_MIXED             //-//
                                : tion3s_state_t::GATE_POSITION_OUTDOOR           //-//
                      ),
        flags({
            .heater_state = state.heater_state,
            .power_state = state.power_state,
            .timer_state = {},
            .sound_state = state.sound_state,
            .ma_auto = state.auto_state,
            .ma_connected = state.auto_state,
            .save = {},
            .ma_pairing = {},
            // в tion remote всегда выставляется этот бит
            .preset_state = true,
            .presets_state = {},
            .reserved = {},
        }),
        filter_time({}),
        factory_reset(false),
        service_mode(false) {}
};

#pragma pack(pop)

}  // namespace tion_3s
}  // namespace dentra
