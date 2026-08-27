#include <utility>
#include <cstring>
#include <cstdlib>
#include <cstdint>

#include "utils.h"
#include "log.h"

#include "tion-api-defines.h"
#include "tion-api-internal.h"
#include "tion-api-lt-internal.h"
#include "tion-api-uart-lt.h"

/*
logenable noit\r\n
\tLog Is Enabled\r\n

getstate\r\n
\r\n
Current Mode: Work   \r\n"
Current Mode: StandBy\r\n
Speed: %d\r\n
Sensors T_set: %d, T_In: %d, T_out: %d \r\n
PID_Value: %d %d\r\n
Filter Time: %d\r\n
Working Time: %d\r\n
Power On Time: %d\r\n
Error register: %d\r\n
MAC: %d %d %d %d %d %d\r\n
Firmware Version 0x%04X\r\n
\r\n
*/

namespace dentra {
namespace tion_lt {

static const char *const TAG = "tion-api-uart-lt";

// включение работы консоли
static const char *const CMD_LOG_ENABLE = "logenable noit\r\n";
// получение текущего состояния бризера
static const char *const CMD_GET_STATE = "getstate\r\n";
// включение бризера
// если была установлена скорость 0, то она автоматически изменится на 1
static const char *const CMD_POWER_ON = "pon\r\n";
// выключение бризера
static const char *const CMD_POWER_OFF = "stby\r\n";
// включение обогревателя
static const char *const CMD_SET_HEATER_ON = "set_heater_state 1\r\n";
// выключение обогревателя
static const char *const CMD_SET_HEATER_OFF = "set_heater_state 0\r\n";
// установка скорости вентилятора (доп параметр: скорость [0:6])
// можно выставить 0 скорость, тогда заслонка останется открытой если бризер включен
static const char *const CMD_SET_SPEED = "set_speed %u\r\n";
// установка температуры обогрева (доп параметр: температура [-128:127])
static const char *const CMD_SET_TEMP = "set_temp %d\r\n";
// сброс до заводских настроек
static const char *const CMD_FACTORY_RESET = "factoryreset\r\n";
// сброс счетчика фильтра, устанавливает значение 15552000 (180 дней)
static const char *const CMD_FILTER_RESET = "ftreset\r\n";
// установка значения счетчика фильтра (доп параметр: кол-во секунд)
static const char *const CMD_SET_FILTER_TIME = "set_filtertime %" PRIu32 "\r\n";
// включение звуковых оповещений
static const char *const CMD_SET_SOUND_STATE_ON = "set_sound_state 1\r\n";
// выключение звуковых оповещений
static const char *const CMD_SET_SOUND_STATE_OFF = "set_sound_state 0\r\n";
// включение световых оповещений
static const char *const CMD_SET_LED_STATE_ON = "set_led_state 1\r\n";
// выключение световых оповещений
static const char *const CMD_SET_LED_STATE_OFF = "set_led_state 0\r\n";

//
// Дополнительные неиспользуемые команды
//

// увеличение скорости вентиляции, не поднимает выше 6
static const char *const CMD_SPEED_UP = "spup\r\n";
// уменьшение скорости вентиляции, не опускает ниже 1
static const char *const CMD_SPEED_DOWN = "spdw\r\n";
// увеличение целевой температуры нагрева, максимально 127
static const char *const CMD_TEMP_UP = "tup\r\n";
// уменьшение целевой температуры нагрева, не опускает ниже 0
static const char *const CMD_TEMP_DOWN = "tdw\r\n";
// перезагрузка бризера
// приведет к выключению бризера и отключает консоль
static const char *const CMD_REBOOT = "reboot\r\n";
// установка счетчика работы вентилятора (доп параметр кол-во секунд)
static const char *const CMD_FAN_TIME = "set_worktime %" PRIu32 "\r\n";
// включение режима сопряжения BLE
static const char *const CMD_BLE_PAIR = "pair\r\n";
// отключает все подключенные BLE устройства
static const char *const CMD_BLE_FORCE_DISCONNECT = "bledis\r\n";
// предположительно проводит внутренний тест
// параметром запрашивает:
// Set test type: need value
// Available types:
// 0 - Stop test
// 1 - Default test
// 2 - Gate test
// 3 - Heater test
// 4 - Triac test
// 5 - LED test
// 6 - Resourse test
static const char *const CMD_SELF_TEST = "selftest\r\n";
// предположительно проводит внутренний тест памяти, операция занимает продолжительное время,
// по окончании выводит стандартный ответ состояния
static const char *const CMD_MEMORY_TEST = "memtest\r\n";
// результат работы команды неизвестен, команде требуются какие-то параметры
static const char *const CMD_SET_PID = "set_pid\r\n";
// результат работы команды неизвестен, команде требуются какие-то параметры
static const char *const CMD_GET_PID = "get_pid\r\n";

#define ST_MODE "Current Mode: "
#define ST_SPEED "Speed: "
#define ST_SENS "Sensors T_set: "
#define ST_HEAT "PID_Value: "
#define ST_FLT_TIME "Filter Time: "
#define ST_FAN_TIME "Working Time: "
#define ST_WRK_TIME "Power On Time: "
#define ST_ERROR "Error register:"
#define ST_MAC "MAC: "
#define ST_FIRM "Firmware Version 0x"

#define ST_SENS_OUTDOOR ", T_In: "
#define ST_SENS_INDOOR ", T_out: "

static const uint8_t PROD[] = {0, TION_LT_AUTO_PROD};

#define TION_LT_TRACE TION_LOGD
#define TION_LT_DUMP TION_LOGD

void TionLtUartProtocol::read_uart_data(tion::TionUartReader *io) {
  if (!this->reader) {
    TION_LOGE(TAG, "Reader is not configured");
    return;
  }

  while (io->available() > 0) {
    if (this->read_frame_(io) == READ_NEXT_LOOP) {
      break;
    }
    tion::yield();
  }
}

TionLtUartProtocol::read_frame_result_t TionLtUartProtocol::read_frame_(tion::TionUartReader *io) {
  auto *buf = this->buf_;
  auto *end = this->buf_ + sizeof(this->buf_) - 1;
  while (buf < end) {
    if (!io->read_array(buf, 1)) {
      TION_LOGW(TAG, "Failed read message");
      this->reset_buf_();
      return READ_NEXT_LOOP;
    }
    if (*buf == '\n') {
      if (buf > this->buf_ && *(buf - 1) == '\r') {
        *(buf - 1) = 0;
      } else {
        *buf = 0;
      }
      break;
    }
    buf++;
  }

  if (buf == end) {
    TION_LOGW(TAG, "Message is too long: %s", this->buf_);
    this->reset_buf_();
    return READ_NEXT_LOOP;
  }

  if (*this->buf_ == 0) {
    this->reset_buf_();
    return READ_NEXT_LOOP;
  }

  auto *str = reinterpret_cast<const char *>(this->buf_);
  TION_LT_TRACE(TAG, "RX: %s", str);
  if (std::strncmp(str, ST_MODE, sizeof(ST_MODE) - 1) == 0) {
    // StandBy or Work
    str = str + sizeof(ST_MODE) - 1;
    this->t_data.power_state = *str == 'W';  // "W" - is a first of "Work"
  } else if (std::strncmp(str, ST_SPEED, sizeof(ST_SPEED) - 1) == 0) {
    str = str + sizeof(ST_SPEED) - 1;
    this->t_data.fan_speed = std::strtol(str, nullptr, 10);
    TION_LT_DUMP(TAG, "Got fan : %d", this->t_data.fan_speed);
  } else if (std::strncmp(str, ST_SENS, sizeof(ST_SENS) - 1) == 0) {
    str = str + sizeof(ST_SENS) - 1;
    char *end{};
    this->t_data.target_temperature = std::strtol(str, &end, 10);
    if ((str = end) && std::strncmp(str, ST_SENS_OUTDOOR, sizeof(ST_SENS_OUTDOOR) - 1) == 0) {
      str = end + sizeof(ST_SENS_OUTDOOR) - 1;
      end = {};
      this->t_data.outdoor_temperature = std::strtol(str, &end, 10);
      if ((str = end) && std::strncmp(str, ST_SENS_INDOOR, sizeof(ST_SENS_INDOOR) - 1) == 0) {
        str = end + sizeof(ST_SENS_INDOOR) - 1;
        this->t_data.current_temperature = std::strtol(str, nullptr, 10);
      }
    }
    TION_LT_DUMP(TAG, "Got sens: target=%d, outdoor=%d, current=%d", this->t_data.target_temperature,
                 this->t_data.outdoor_temperature, this->t_data.current_temperature);
  } else if (std::strncmp(str, ST_HEAT, sizeof(ST_HEAT) - 1) == 0) {
    str = str + sizeof(ST_HEAT) - 1;
    char *end{};
    this->t_data.heater_var = std::strtoul(str, &end, 10);
    if (end) {
      this->t_data.heater_state = std::strtoul(end, nullptr, 10);
    }
    TION_LT_DUMP(TAG, "Got heat: var=%u, state=%s", this->t_data.heater_var, ONOFF(this->t_data.heater_state));
  } else if (std::strncmp(str, ST_FLT_TIME, sizeof(ST_FLT_TIME) - 1) == 0) {
    str = str + sizeof(ST_FLT_TIME) - 1;
    this->t_data.filter_time = std::strtoul(str, nullptr, 10);
    TION_LT_DUMP(TAG, "Got tflt: %s", str);
  } else if (std::strncmp(str, ST_FAN_TIME, sizeof(ST_FAN_TIME) - 1) == 0) {
    str = str + sizeof(ST_FAN_TIME) - 1;
    const uint32_t fan_time = std::strtoul(str, nullptr, 10);
    // время работы вентилятора приходит после скорости, поэтому можно
    // рассчитать airflow_counter
    const uint32_t dif_ft = fan_time - this->t_data.fan_time;
    const uint32_t dif_ac = dif_ft * PROD[this->t_data.fan_speed] / tion_lt_state_counters_t::AK;
    this->t_data.airflow_counter += dif_ac;
    this->t_data.fan_time = fan_time;
    TION_LT_DUMP(TAG, "Got twrk: %s", str);
  } else if (std::strncmp(str, ST_WRK_TIME, sizeof(ST_WRK_TIME) - 1) == 0) {
    str = str + sizeof(ST_WRK_TIME) - 1;
    this->t_data.work_time = std::strtoul(str, nullptr, 10);
    TION_LT_DUMP(TAG, "Got tpwr: %s", str);
  } else if (std::strncmp(str, ST_ERROR, sizeof(ST_ERROR) - 1) == 0) {
    str = str + sizeof(ST_ERROR) - 1;
    TION_LT_DUMP(TAG, "Got err : %s", str);
    // это последняя нужная строка при получении состояния
    tion::tion_frame_t<tionlt_state_get_req_t> frame{.type = FRAME_TYPE_STATE_RSP, .data{}};
    frame.data.state.power_state = t_data.power_state;
    frame.data.state.heater_state = t_data.heater_state;
    frame.data.state.fan_speed = t_data.fan_speed;
    frame.data.state.target_temperature = t_data.target_temperature;
    frame.data.state.outdoor_temperature = t_data.outdoor_temperature;
    frame.data.state.current_temperature = t_data.current_temperature;
    frame.data.state.heater_var = t_data.heater_var;
    frame.data.state.counters.work_time = t_data.work_time;
    frame.data.state.counters.fan_time = t_data.fan_time;
    frame.data.state.counters.filter_time = t_data.filter_time;
    frame.data.state.errors = std::strtoul(str, nullptr, 10);

    // calculated data
    frame.data.state.counters.airflow_counter = t_data.airflow_counter;
    frame.data.state.filter_state = frame.data.state.counters.filter_time_left_d() <= 30;
    frame.data.state.heater_present = true;
    frame.data.state.gate_state = t_data.power_state ? tionlt_state_t::OPENED : tionlt_state_t::CLOSED;
    frame.data.state.max_fan_speed = 6;
    // frame.data.state.pcb_temperature = INT8_MIN;

    this->reader(*reinterpret_cast<const tion::tion_any_frame_t *>(&frame), sizeof(frame));
  } else if (std::strncmp(str, ST_FIRM, sizeof(ST_FIRM) - 1) == 0) {
    str = str + sizeof(ST_FIRM) - 1;
    tion::tion_frame_t<tion::tion_dev_info_t> frame{
        .type = FRAME_TYPE_DEV_INFO_RSP,
        .data{
            .work_mode = tion::tion_dev_info_t::NORMAL,
            .device_type = tion::tion_dev_info_t::BRLT,
            .firmware_version = static_cast<uint16_t>(std::strtoul(str, nullptr, 16)),
            .hardware_version = {},
            .reserved = {},
        },
    };
    TION_LT_DUMP(TAG, "Got frm : %04X", frame.data.firmware_version);
    this->reader(*reinterpret_cast<const tion::tion_any_frame_t *>(&frame), sizeof(frame));
  } else {
    TION_LOGW(TAG, "Unsupported: %s", this->buf_);
  }

  this->reset_buf_();
  return READ_NEXT_LOOP;
}

bool TionLtUartProtocol::write_frame(uint16_t type, const void *data, size_t size) {
  if (!this->writer) {
    TION_LOGE(TAG, "Writer is not configured");
    return false;
  }

  switch (type) {
    case FRAME_TYPE_DEV_INFO_REQ: {
      // эта команда будет перед запуском запроса состояния.
      // тут и запросим включение лога
      return this->write_cmd_(CMD_LOG_ENABLE);
    }

    case FRAME_TYPE_STATE_REQ: {
      return this->write_cmd_(CMD_GET_STATE);
    }

    case FRAME_TYPE_STATE_SET: {
      const auto &set = static_cast<const tionlt_state_set_req_t *>(data)->data;

      if (set.filter_reset) {
        if (set.filter_time) {
          // filter_time в днях, переведем в секунды
          const uint32_t filter_time_seconds = static_cast<uint32_t>(set.filter_time) * (60UL * 60UL * 24UL);
          return this->write_cmd_(CMD_SET_FILTER_TIME, filter_time_seconds);
        }
        // сбрасываем в значение по-умолчанию (180 дней = 15552000 сек)
        return this->write_cmd_(CMD_FILTER_RESET);
      }

      if (set.factory_reset) {
        return this->write_cmd_(CMD_FACTORY_RESET);
      }

      if (set.error_reset) {
        TION_LOGW(TAG, "error_reset is not supported yet");
        return false;
      }

      bool has_changes = false;

      if (this->t_data.fan_speed != set.fan_speed) {
        this->write_cmd_(CMD_SET_SPEED, static_cast<int8_t>(set.fan_speed));
        has_changes = true;
      }
      if (this->t_data.target_temperature != set.target_temperature) {
        this->write_cmd_(CMD_SET_TEMP, set.target_temperature);
        has_changes = true;
      }
      if (this->t_data.heater_state != set.heater_state) {
        this->write_cmd_(set.heater_state ? CMD_SET_HEATER_ON : CMD_SET_HEATER_OFF);
        has_changes = true;
      }
      if (this->t_data.sound_state != set.sound_state) {
        // команду можем выполнить, но состояние прочитать не можем
        this->write_cmd_(set.sound_state ? CMD_SET_SOUND_STATE_ON : CMD_SET_SOUND_STATE_OFF);
        has_changes = true;
      }
      if (this->t_data.led_state != set.led_state) {
        // команду можем выполнить, но состояние прочитать не можем
        this->write_cmd_(set.led_state ? CMD_SET_LED_STATE_ON : CMD_SET_LED_STATE_OFF);
        has_changes = true;
      }
      if (this->t_data.power_state != set.power_state) {
        this->write_cmd_(set.power_state ? CMD_POWER_ON : CMD_POWER_OFF);
        has_changes = true;
      }

      if (!has_changes) {
        this->write_cmd_(CMD_GET_STATE);
      }

      return true;
    }

    default:
      TION_LOGW(TAG, "Unsupported command: %04X", type);
      break;
  }

  return false;
}

bool TionLtUartProtocol::write_cmd_(const char *cmd) {
  TION_LT_TRACE(TAG, "TX: %s", cmd);
  return this->writer(reinterpret_cast<const uint8_t *>(cmd), strlen(cmd));
}

bool TionLtUartProtocol::write_cmd_(const char *cmd, int8_t param) {
  const auto data = tion::str_sprintf(cmd, param);
  TION_LT_TRACE(TAG, "TX: %s", data.c_str());
  return this->writer(reinterpret_cast<const uint8_t *>(data.c_str()), data.length());
}

bool TionLtUartProtocol::write_cmd_(const char *cmd, uint32_t param) {
  const auto data = tion::str_sprintf(cmd, param);
  TION_LT_TRACE(TAG, "TX: %s", data.c_str());
  return this->writer(reinterpret_cast<const uint8_t *>(data.c_str()), data.length());
}

}  // namespace tion_lt
}  // namespace dentra
