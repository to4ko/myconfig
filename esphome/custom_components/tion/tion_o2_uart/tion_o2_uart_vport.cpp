#include "esphome/core/log.h"
#include "esphome/core/defines.h"

#include "tion_o2_uart_vport.h"

namespace esphome {
namespace tion {

static const char *const TAG = "tion_o2_uart_vport";

void TionO2UartVPort::dump_config() { VPORT_UART_LOG("Tion O2 UART"); }

}  // namespace tion
}  // namespace esphome
