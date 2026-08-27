#pragma once

#include "tion-api-uart.h"

namespace dentra {
namespace tion_lt {

class TionLtUartProtocol : public tion::TionUartProtocolBase<45> {
 public:
  void read_uart_data(tion::TionUartReader *io);

  bool write_frame(uint16_t type, const void *data, size_t size);

 protected:
  struct {
    struct {
      bool power_state : 1;
      bool heater_state : 1;
      bool sound_state : 1;
      bool led_state : 1;
      uint8_t reserved : 4;
    };
    uint8_t fan_speed;
    int8_t target_temperature;
    int8_t outdoor_temperature;
    int8_t current_temperature;
    uint8_t heater_var;
    uint32_t work_time;
    uint32_t fan_time;
    uint32_t filter_time;
    uint32_t airflow_counter;
  } t_data{};
  /// Reads a frame starting with size for hw uart or continue reading for sw uart
  read_frame_result_t read_frame_(tion::TionUartReader *io);

  bool write_cmd_(const char *cmd);
  bool write_cmd_(const char *cmd, int8_t param);
  bool write_cmd_(const char *cmd, uint32_t param);
};

}  // namespace tion_lt
}  // namespace dentra
