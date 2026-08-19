#include "transport_factory.h"
#include "transport_interface.h"
#include "transport_simulation.h"
#ifdef USE_ESP32
#include "transport_esp32.h"
#endif

namespace esphome {
namespace ups_hid {

std::unique_ptr<IUsbTransport> UsbTransportFactory::create(TransportType type, bool simulation_mode) {
    if (simulation_mode || type == SIMULATION) {
        return std::make_unique<SimulatedTransport>();
    }
    
#ifdef USE_ESP32
    if (type == ESP32_HARDWARE) {
        return std::make_unique<Esp32UsbTransport>();
    }
#endif

    // Default fallback to simulation if ESP32 not available
    return std::make_unique<SimulatedTransport>();
}

} // namespace ups_hid
} // namespace esphome