#pragma once
#include <cstdint>

#include "tion-api-internal.h"

namespace dentra {
namespace tion_o2 {

enum : uint16_t {
  // 00
  FRAME_TYPE_CONNECT_REQ = 0x00,
  FRAME_TYPE_CONNECT_RSP = 0x10,

  // 01
  FRAME_TYPE_STATE_GET_REQ = 0x01,
  FRAME_TYPE_STATE_GET_RSP = 0x11,
  // 02
  FRAME_TYPE_STATE_SET_REQ = 0x02,

  // 03
  FRAME_TYPE_DEV_MODE_REQ = 0x03,
  FRAME_TYPE_DEV_MODE_RSP = 0x13,

  // 04
  FRAME_TYPE_SET_WORK_MODE_REQ = 0x04,
  FRAME_TYPE_SET_WORK_MODE_RSP = 0x55,

  // 05
  FRAME_TYPE_TIME_GET_REQ = 0x05,
  FRAME_TYPE_TIME_GET_RSP = 0x15,
  // 06
  FRAME_TYPE_TIME_SET_REQ = 0x06,

  // 07
  FRAME_TYPE_DEV_INFO_REQ = 0x07,
  FRAME_TYPE_DEV_INFO_RSP = 0x17,
};

#pragma pack(push, 1)
// 11 0C FE 0D 0A 02 3C 04
// 00 00 E0 D7 DC 01 21 F4
// CA 01 D5
// Ответ 11:
// Байт 0 - команда 11
// Байт 2 - температура
// Байт 4 - нагрев
// NOLINTNEXTLINE(readability-identifier-naming)
struct tiono2_state_t {
  enum { ERROR_MIN_BIT = 0, ERROR_MAX_BIT = 10, GATE_ERROR_BIT = 1 << 4 };

  // Байт 1.
  union {
    struct {
      bool filter_state : 1;
      bool power_state : 1;
      bool unknown2_state : 1;
      bool heater_state : 1;
      uint8_t reserved_state : 4;
    };
    uint8_t flags;
  };
  // Байт 2. Температура до нагревателя.
  int8_t outdoor_temperature;
  // Байт 3. Температура после нагревателя.
  int8_t current_temperature;
  // Байт 4. Целевая температура [-20:25].
  int8_t target_temperature;
  // Байт 5. Скорость вентиляции [1-4].
  uint8_t fan_speed;
  // Байт 6. Производительность бризера в m3.
  uint8_t productivity;
  // Байт 7. Всегда 0x04 - возможно максимально-допустимая скорость вентиляции.
  uint8_t unknown7;
  // Байт 8,9.
  uint16_t errors;
  // Байт 10,11. Время наработки в секундах.
  uint32_t work_time;
  // Байт 12,13. Остаток ресурса фильтра в секундах.
  uint32_t filter_time;

  static std::string decode_errors(uint32_t errors) {
    return tion::decode_errors(errors, ERROR_MIN_BIT, ERROR_MAX_BIT, 0, 0);
  }
  static void report_errors(uint32_t errors);
};

static_assert(sizeof(tiono2_state_t) == 17, "Invalid tiono2_state_t size");

struct tiono2_time_t {
  uint8_t hours;
  uint8_t minutes;
  uint8_t seconds;
};

static_assert(sizeof(tiono2_time_t) == 3, "Invalid tiono2_time_t size");

struct tiono2_state_set_t {
  // Байт 1. Скорость вентиляции [1:4].
  uint8_t fan_speed;
  // Байт 2. Целевая температура [-20:25].
  int8_t target_temperature;
  // Байт 3., 0 off, 1 on 4
  struct {
    bool power_state : 8;
  };
  // Байт 4.
  struct {
    bool heater_state : 8;
  };
  // Байт 5. Возможно источник:  0 - auto, 1 - user
  // большое подозрение, что это эквивалент last_com_source
  tion::CommSource comm_source;

  tiono2_state_set_t() = delete;
  tiono2_state_set_t(const tion::TionState &state)
      : fan_speed(state.fan_speed == 0 ? static_cast<uint8_t>(1) : state.fan_speed),
        target_temperature(state.target_temperature),
        power_state(state.power_state),
        heater_state(state.heater_state),
        comm_source(state.comm_source) {}
};

static_assert(sizeof(tiono2_state_set_t) == 5, "Invalid tiono2_state_set_t size");

// 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25
// 17 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 08 61 0E 13 04 10 EC 19 79
struct tiono2_dev_info_t {
  // Байт 1. Всегда 0x04 - возможно максимально-допустимая скорость вентиляции.
  uint8_t unknown1;
  // Байт 2-16. заполнено 00
  uint8_t unknown2_16[15];
  // Байт 17,18. Версия железа бризера.
  uint16_t hardware_version;
  // Байт 19,20. Версия прошивки бризера.
  uint16_t firmware_version;
  // Байт 21. Всегда 0x04 - возможно максимально-допустимая скорость вентиляции.
  uint8_t unknown21;
  // Байт 22.
  uint8_t unknown22;
  // Байт 23. Минимальная температура нагревателя.
  int8_t heater_min;
  // Байт 24. Максимальная температура нагревателя.
  int8_t heater_max;
};

static_assert(sizeof(tiono2_dev_info_t) == 24, "Invalid tiono2_dev_info_t size");

// Состояние девайса, получается от бризера командой FRAME_TYPE_DEV_MODE_RSP.
struct DevModeFlags {
  // Бит 0. Включен в моменте сопряжения.
  bool pair : 1;
  // Бит 1. Включен, если управление было физическими кнопками на бризере.
  bool user : 1;
  // Бит 2-7. Назначение на данный момент неизвестно, возможно зарезервировано.
  uint8_t reserved : 6;
};

// Состояние режима работы, передается бризеру командой FRAME_TYPE_SET_WORK_MODE_REQ.
struct WorkModeFlags {
  // Бит 0. Возможно признак подтверждения, что принят режим сопряжения.
  // включение/выключение этого флага заставляет бризер издать звук и поморгать экраном
  bool ma_pair_accepted : 1;
  // Бит 1. Установлен когда RF-модуль подключен.
  bool rf_connected : 1;
  // Бит 2. Возможно устанавливается во время сопряжения с MA.
  bool ma_pairing : 1;
  // Бит 3. Установлен когда включен режим AUTO на MA.
  // светится соответствующим значком на экране бризера
  bool ma_auto : 1;
  // Бит 4. Установлен когда станция MA подключена.
  // светится соответствующим значком на экране бризера
  bool ma_connected : 1;
  // Бит 5,6,7. Назначение на данный момент неизвестно, возможно зарезервировано.
  uint8_t reserved : 3;
};

#pragma pack(pop)

}  // namespace tion_o2
}  // namespace dentra
