#pragma once

#include "transport_interface.h"

namespace esphome {
namespace ups_hid {

/**
 * Factory for creating USB transport instances
 */
class UsbTransportFactory {
public:
    enum TransportType {
        ESP32_HARDWARE,
        SIMULATION
    };
    
    static std::unique_ptr<IUsbTransport> create(TransportType type, 
                                               bool simulation_mode = false);
};

} // namespace ups_hid
} // namespace esphome