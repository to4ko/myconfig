#pragma once

#include <cstdint>

namespace dentra {
namespace tion_iq {

enum {
  FRAME_TYPE_STATE_SET = 0x3230,
  FRAME_TYPE_STATE_RSP = 0x3231,
  FRAME_TYPE_STATE_REQ = 0x3232,

  FRAME_TYPE_DEV_INFO_REQ = 0x3332,
  FRAME_TYPE_DEV_INFO_RSP = 0x3331,
};

struct tioniq_state_t {
  struct {
    // Байт 0, бит 0.
    bool power_state : 1;
    // Байт 0, бит 1.
    bool sound_state : 1;
    // Байт 0, бит 2-3. принимает значения 0, 1, 2, 3.
    uint8_t led_state : 2;
    // Байт 0, бит 4.
    bool lock_state : 1;
    // Байт 0, бит 5-6.
    uint8_t unknown0_5_7 : 3;
  };
  struct {
    // Байт 1, бит 0-1.
    uint8_t unknown1_0_1 : 2;
    // Байт 1, бит 2.
    bool ma_auto : 1;
    // Байт 1, бит 3.
    bool timer_state : 1;
    // Байт 1, бит 4-7.
    uint8_t unknown1_4_7 : 4;
  };
  // Байт 2.
  uint8_t unknown2;
  // Байт 3.
  uint8_t fan_speed;
  // Байт 4.
  uint8_t timer;
  // Байт 5-6.
  uint16_t pm_value;
  // Байт 7-8.
  uint16_t voc_value;
  // Байт 9-16.
  uint8_t unknown9_16[8];
  // Байт 17-20.
  uint32_t filter_time;
};

}  // namespace tion_iq
}  // namespace dentra
