#pragma once

#include "esp_err.h"
#include <vector>
#include <cstdint>
#include <memory>

namespace esphome {
namespace ups_hid {

/**
 * Abstract USB Transport Interface
 * 
 * Provides a clean abstraction over USB communication, allowing for
 * different implementations (ESP32 hardware, simulation, etc.)
 * 
 * Design Pattern: Strategy Pattern for transport selection
 */
class IUsbTransport {
public:
    virtual ~IUsbTransport() = default;
    
    // Transport lifecycle
    virtual esp_err_t initialize() = 0;
    virtual esp_err_t deinitialize() = 0;
    
    // Device management
    virtual bool is_connected() const = 0;
    virtual uint16_t get_vendor_id() const = 0;
    virtual uint16_t get_product_id() const = 0;
    
    // HID communication
    virtual esp_err_t hid_get_report(uint8_t report_type, uint8_t report_id, 
                                   uint8_t* data, size_t* data_len, 
                                   uint32_t timeout_ms = 1000) = 0;
    
    virtual esp_err_t hid_set_report(uint8_t report_type, uint8_t report_id,
                                   const uint8_t* data, size_t data_len,
                                   uint32_t timeout_ms = 1000) = 0;

    // Interrupt IN transfer read (as opposed to a control-transfer
    // GET_REPORT). Some HID-tunneling USB-to-serial bridges (notably
    // Cypress-based Megatec/Q1 UPS adapters, used by many Ippon and similar
    // units) don't respond usefully to GET_REPORT control transfers at all
    // - the actual response has to be read from the device's interrupt IN
    // endpoint, matching how NUT's blazer_usb "cypress" subdriver works.
    // Sending GET_REPORT to such a device instead of reading the interrupt
    // endpoint has been observed to stall the ESP32 USB host stack badly
    // enough to trip the task watchdog, so protocols must not fall back to
    // hid_get_report() for these devices.
    virtual esp_err_t hid_interrupt_read(uint8_t* data, size_t* data_len,
                                       uint32_t timeout_ms = 1000) = 0;
    
    // String descriptors
    virtual esp_err_t get_string_descriptor(uint8_t string_index, 
                                          std::string& result) = 0;
    
    // Error information
    virtual std::string get_last_error() const = 0;
};

// Forward declaration - implementation in usb_transport_factory.h
class UsbTransportFactory;

} // namespace ups_hid
} // namespace esphome