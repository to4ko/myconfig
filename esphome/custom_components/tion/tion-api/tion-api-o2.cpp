#include <cinttypes>

#include "log.h"
#include "utils.h"
#include "tion-api-o2.h"
#include "tion-api-defines.h"

/*
21.01.2023 20:58 (внешняя температура в мск T=-10 (0xF6) T=-12 (0xF4) Td=-13 (0xF3))
Через 1.138 сек. после запуска
    RF модуль: 00 ff
    Бризер: 10 04 10 01 00 FA
    RF модуль: 07 F8
    Бризер: 17 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 08 61 0E 13 04 10 EC 19 79
    RF модуль: 01 FE
            00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18
    Бризер: 11 0С 14 17 10 02 3С 04 00 00 04 0А ВС 01 47 73 СВ 01 E3

Через ~200 мс и каждые 200 мс.
    RF модуль: 03 FC
    Бризер: 13 00 EC
    RF модуль: 04 00 FB
    Бризер: 55 AA

22.01.2023 23:07 (внешняя температура в мск T=-10 (0xF6))
## Если RF модуль не подключён к бризеру

    0. pause ~1137 msec
    1. RF модуль: 00 FF
    2. pause ~10 msec
    3. RF модуль: 00 FF
    4. pause ~10 msec
    5. RF модуль: 00 FF
    6. pause ~210 msec
    7. GOTO 1

## Если RF модуль подключен к бризеру
0.  pause ~1138 msec
1.  RF модуль: 00 FF
2.  Бризер: 10 04 10 01 00 FA
3.  RF модуль: 07 F8
4.  Бризер: 17 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 08 61 0E 13 04 10 EC 19 79
5.  RF модуль: 01 FE
            00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18
6.  Бризер: 11 0C 0C 13 10 02 3C 04 00 00 B4 D6 DC 01 01 F6 CA 01 54
            11 0C 0F 15 10 02 3C 04 00 00 B4 D6 DC 01 01 F6 CA 01 51
            11 0C 11 16 10 02 3C 04 00 00 B4 D6 DC 01 01 F6 CA 01 4C
            11 0C FF 0D 10 04 78 04 00 00 F0 D6 DC 01 89 F5 CA 01 34 (температура 0 или 1, нагрев 16)
            11 0C FD 10 10 04 78 04 00 00 2C D7 DC 01 11 F5 CA 01 6E (температура -3 или -4, нагрев 16)
            11 0C FE 0F 10 02 3C 04 00 00 68 D7 DC 01 99 F4 CA 01 FD (температура -2 или -3, нагрев 16)
            11 0C FE 0D 0A 02 3C 04 00 00 E0 D7 DC 01 21 F4 CA 01 D5 (температура -2 или -3, нагрев 10)
7.  pause ~200 msec
8.  RF модуль: 03 FC
9.  Бризер: 13 00 EC
10. RF модуль: 04 00 FB
11. Бризер: 55 AA
12. GOTO 7
*/

namespace dentra {
namespace tion_o2 {

using namespace tion;

static const char *const TAG = "tion-api-uart-o2";

static const uint8_t PROD[] = {0, TION_O2_AUTO_PROD};

constexpr size_t ERRORS_COUNT = tiono2_state_t::ERROR_MAX_BIT - tiono2_state_t::ERROR_MIN_BIT + 1;
static const char *const ERRORS[ERRORS_COUNT] = {
    // EC01
    "Температура входящего воздуха более +50 °C",
    // EC02
    "Температура уличного воздуха ниже значения, установленного параметром «Минимальная допустимая температура»",
    // EC03
    "Температура выходящего воздуха более +50 °C",
    // EC04
    "Значение температуры выходящего воздуха ниже 25 °C (при включенном нагревателе)",
    // EC05
    "Ошибка работы заслонки",
    // EC06
    "Переохлаждение платы управления или индикации",
    // EC07
    "Цепь датчика NTC температуры наружного воздуха короткозамкнута",
    // EC08
    "Обрыв в цепи датчика NTC температуры воздуха после нагревателя",
    // EC09
    "Цепь датчика NTC температуры воздуха, поступающего в прибор, короткозамкнута",
    // EC10
    "Обрыв в цепи датчика NTC температуры воздуха, поступающего в прибор",
    // EC11
    "Сбой передачи данных между силовой платой и платой управления",
};

void tiono2_state_t::report_errors(uint32_t errors) {
  enum_errors(errors, tiono2_state_t::ERROR_MIN_BIT, tiono2_state_t::ERROR_MAX_BIT, nullptr,
              [](uint8_t err, const void *) {
                if (err > 0 && (err - 1) < ERRORS_COUNT) {
                  TION_REPORT_EC(TAG, err, ERRORS[err - 1]);
                } else {
                  TION_REPORT_EC_UNK(TAG, err);
                }
              });
}

size_t get_req_frame_size(uint8_t frame_type) {
  if (frame_type == FRAME_TYPE_DEV_MODE_REQ) {
    return 1;
  }
  if (frame_type == FRAME_TYPE_SET_WORK_MODE_REQ) {
    return 2;
  }
  if (frame_type == FRAME_TYPE_STATE_GET_REQ) {
    return 1;
  }
  if (frame_type == FRAME_TYPE_STATE_SET_REQ) {
    // 02 01 EC 01 01 01 11
    return 6;
  }
  if (frame_type == FRAME_TYPE_DEV_INFO_REQ) {
    return 1;
  }
  if (frame_type == FRAME_TYPE_CONNECT_REQ) {
    return 1;
  }
  if (frame_type == FRAME_TYPE_TIME_GET_REQ) {
    return 1;
  }
  if (frame_type == FRAME_TYPE_TIME_SET_REQ) {
    // 06 16 34 09 D2
    return 3;
  }
  return 0;
}

size_t get_rsp_frame_size(uint8_t frame_type) {
  if (frame_type == FRAME_TYPE_DEV_MODE_RSP) {
    // 13 00 EC
    return 2;
  }
  if (frame_type == FRAME_TYPE_SET_WORK_MODE_RSP) {
    // 55 AA
    return 1;
  }
  if (frame_type == FRAME_TYPE_STATE_GET_RSP) {
    // 11 0C FE 0D 0A 02 3C 04
    // 00 00 E0 D7 DC 01 21 F4
    // CA 01 D5
    return 18;
  }
  if (frame_type == FRAME_TYPE_DEV_INFO_RSP) {
    // 17 04 00 00 00 00 00 00
    // 00 00 00 00 00 00 00 00
    // 00 08 61 0E 13 04 10 EC
    // 19 79
    return 25;
  }
  if (frame_type == FRAME_TYPE_CONNECT_RSP) {
    // 10 04 10 01 00 FA
    return 5;
  }
  if (frame_type == FRAME_TYPE_TIME_GET_RSP) {
    // 15 16 34 09 C1
    return 4;
  }
  return 0;
}

void TionO2Api::read_frame(uint16_t frame_type, const void *frame_data, size_t frame_data_size) {
  if (frame_type == FRAME_TYPE_STATE_GET_RSP) {
    TION_LOGD(TAG, "Response State Get");
    auto *frame = static_cast<const tiono2_state_t *>(frame_data);
    this->update_state_(*frame);
    this->notify_state_(0);
    return;
  }

  if (frame_type == FRAME_TYPE_DEV_MODE_RSP) {
    // 13 00 EC
    struct RawDevModeFrame {
      union {
        DevModeFlags dev_mode;
        uint8_t data;
      };
    } PACKED;
    auto *frame = static_cast<const RawDevModeFrame *>(frame_data);
    TION_LOGD(TAG, "Response Dev mode: %s", tion::get_flag_bits(frame->data));
    this->update_dev_mode_(frame->dev_mode);
    return;
  }

  if (frame_type == FRAME_TYPE_SET_WORK_MODE_RSP) {
    // 55 AA
    TION_LOGV(TAG, "Response Work Mode");
    return;
  }

  if (frame_type == FRAME_TYPE_DEV_INFO_RSP) {
    // 17 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 08 61 0E 13 04 10 EC 19 79
    TION_LOGD(TAG, "Response Device info: %s", hex_cstr(frame_data, frame_data_size));
    this->update_dev_info_(*static_cast<const tiono2_dev_info_t *>(frame_data));
    return;
  }

  if (frame_type == FRAME_TYPE_CONNECT_RSP) {
    // 10 04 10 01 00 FA
    TION_LOGD(TAG, "Response Connect: %s", hex_cstr(frame_data, frame_data_size));
    return;
  }

  if (frame_type == FRAME_TYPE_TIME_GET_RSP) {
    // 15 0B 09 1A F2
    auto *data = static_cast<const tiono2_time_t *>(frame_data);
    TION_LOGD(TAG, "Response Time: %02u:%02u:%02u", data->hours, data->minutes, data->seconds);
    return;
  }

  TION_LOGW(TAG, "Unsupported frame %02X: %s", frame_type, hex_cstr(frame_data, frame_data_size));
}

bool TionO2Api::request_connect_() const {
  TION_LOGD(TAG, "Request Connect");
  return this->write_frame(FRAME_TYPE_CONNECT_REQ);
}

bool TionO2Api::request_dev_info_() const {
  TION_LOGD(TAG, "Request Device info");
  return this->write_frame(FRAME_TYPE_DEV_INFO_REQ);
}

bool TionO2Api::request_state_() const {
  TION_LOGD(TAG, "Request State Get");
  return this->write_frame(FRAME_TYPE_STATE_GET_REQ);
}

bool TionO2Api::request_dev_mode_() const {
  TION_LOGV(TAG, "Request Dev mode");
  return this->write_frame(FRAME_TYPE_DEV_MODE_REQ);
}

bool TionO2Api::set_work_mode(WorkModeFlags work_mode) const {
  TION_LOGV(TAG, "Request Work mode");
  return this->write_frame(FRAME_TYPE_SET_WORK_MODE_REQ, work_mode);
}

void TionO2Api::write_state(TionStateCall *call) {
  TION_LOGV(TAG, "Request State set");
  const auto st = this->make_write_state_(call);

  // auto_state невозможно получить от бризера
  this->state_.auto_state = st.auto_state;
  // поддержка пищалки в мануальном режиме
  this->state_.sound_state = st.sound_state;

  if (!st.auto_state && st.sound_state) {
    // не пищим в ароматическом режиме.
    // трюк с писком заключается в установке и снятия ma_pair_accepted
    // снимается в update_work_mode
    this->set_work_mode({
        .ma_pair_accepted = true,
        .rf_connected = {},
        .ma_pairing = {},
        .ma_auto = {},
        .ma_connected = {},
        .reserved = 0,
    });
  }

  tiono2_state_set_t req(st);
  TION_DUMP(TAG, "fan  : %u", req.fan_speed);
  TION_DUMP(TAG, "temp : %u", req.target_temperature);
  TION_DUMP(TAG, "power: %s", ONOFF(req.power_state));
  TION_DUMP(TAG, "heat : %s", ONOFF(req.heater_state));
  TION_DUMP(TAG, "comm : %s", req.comm_source == tion::CommSource::AUTO ? "AUTO" : "USER");
  this->write_frame(FRAME_TYPE_STATE_SET_REQ, req);

  if (!st.auto_state && st.sound_state) {
    this->update_work_mode();
  }
}

void TionO2Api::update_work_mode() {
  if (this->state_.auto_state) {
    this->set_work_mode({
        .ma_pair_accepted = {},
        .rf_connected = {},
        .ma_pairing = {},
        .ma_auto = true,
        .ma_connected = {},
        .reserved = 0,
    });
  }
}

bool TionO2Api::reset_filter(const tion::TionState &state, uint32_t request_id) const {
  TION_LOGW(TAG, "reset_filter is not implemented");
  return false;
}

void TionO2Api::request_state() {
  if (this->state_.firmware_version == 0) {
    this->request_connect_();
    this->request_dev_info_();
  }
  this->request_dev_mode_();
  this->request_state_();
}

TionO2Api::TionO2Api() : TionApiBase() {
  this->traits_.errors_decode = tiono2_state_t::decode_errors;
  this->traits_.errors_report = tiono2_state_t::report_errors;

  this->traits_.supports_work_time = true;
  this->traits_.supports_gate_error = true;
#ifdef TION_ENABLE_ANTIFREEZE
  this->traits_.supports_manual_antifreeze = true;
#endif
  this->traits_.supports_sound_state = true;
  this->traits_.max_heater_power = TION_O2_HEATER_POWER;
  this->traits_.max_fan_speed = 4;
  this->traits_.min_target_temperature = -30;
  this->traits_.max_target_temperature = 25;

  this->traits_.max_fan_power[0] = TION_O2_MAX_FAN_POWER0;
  this->traits_.max_fan_power[1] = TION_O2_MAX_FAN_POWER1;
  this->traits_.max_fan_power[2] = TION_O2_MAX_FAN_POWER2;
  this->traits_.max_fan_power[3] = TION_O2_MAX_FAN_POWER3;
  this->traits_.max_fan_power[4] = TION_O2_MAX_FAN_POWER4;

  this->traits_.auto_prod = PROD;
}

void TionO2Api::update_dev_mode_(const DevModeFlags &dev_mode) {
  if (dev_mode.user) {
    // TODO нужно ли отключать auto если пользователь нажал физ кнопку
    // this->state_.auto_state = false;
    this->state_.comm_source = CommSource::USER;
  } else {
    this->state_.comm_source = CommSource::AUTO;
  }
}

void TionO2Api::update_dev_info_(const tiono2_dev_info_t &dev_info) {
  this->traits_.min_target_temperature = dev_info.heater_min;
  this->traits_.max_target_temperature = dev_info.heater_max;
  this->state_.hardware_version = dev_info.hardware_version;
  this->state_.firmware_version = dev_info.firmware_version;
}

void TionO2Api::update_state_(const tiono2_state_t &state) {
  this->state_.initialized = true;

  this->state_.power_state = state.power_state;
  this->state_.heater_state = state.heater_state;
  // this->state_.sound_state = false;
  this->state_.led_state = false;
  // this->state_.comm_source = CommSource::USER;
  // this->state_.auto_state = false;
  this->state_.filter_state = state.filter_state;
  this->state_.gate_error_state = (state.errors & tiono2_state_t::GATE_ERROR_BIT) != 0;
  this->state_.gate_position = state.power_state ? TionGatePosition::OPENED : TionGatePosition::CLOSED;
  this->state_.fan_speed = state.fan_speed;
  this->state_.outdoor_temperature = state.outdoor_temperature;
  this->state_.current_temperature = state.current_temperature;
  this->state_.target_temperature = state.target_temperature;
  this->state_.productivity = state.productivity;
  // this->state_.heater_var = 0;
  this->state_.work_time = state.work_time;
  // this->state_.fan_time = 0;
  this->state_.filter_time_left = state.filter_time;
  // this->state_.airflow_counter = 0;
  // this->traits_.max_heater_power = 1450/10;
  // this->traits_.max_fan_speed = 4;
  // this->traits_.min_target_temperature = -30;
  // this->traits_.min_target_temperature = 25;
  // this->state_.hardware_version = dev_info.hardware_version;
  // this->state_.firmware_version = dev_info.firmware_version;
  // this->state_.pcb_ctl_temperature = 0;
  // this->state_.pcb_pwr_temperature = 0;
  this->state_.errors = state.errors;

  this->dump_state_(state);
}

void TionO2Api::dump_state_(const tiono2_state_t &state) const {
  this->state_.dump(TAG, this->traits_);
  // dump values useful for future research
  TION_DUMP(TAG, "flags       : 0x%02X (%s)", state.flags, tion::get_flag_bits(state.flags));
  if (state.unknown7 != 0x04) {
    TION_LOGW(TAG, "Please report unknown7=%02X", state.unknown7);
  }
}

}  // namespace tion_o2
}  // namespace dentra
