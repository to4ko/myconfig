#pragma once

// Forces the linker to keep this translation unit (and its static fallback-protocol
// registrar) even when building with --gc-sections. Without a real cross-TU symbol
// reference, protocol_generic.cpp.o gets garbage-collected and the generic HID
// fallback silently never registers itself. Call this once, e.g. from
// UpsHidComponent::setup(), before any protocol auto-detection happens.
namespace esphome {
namespace ups_hid {
void ensure_generic_protocol_linked();
}  // namespace ups_hid
}  // namespace esphome


#include "ups_hid.h"
#include "data_composite.h"
#include "data_device.h"
#include <set>
#include <map>

namespace esphome {
namespace ups_hid {

/**
 * Generic HID Protocol Implementation
 * 
 * Provides fallback support for unknown UPS vendors by attempting to
 * discover and parse common HID Power Device report IDs.
 * 
 * This protocol uses a discovery-based approach, testing standard report IDs
 * that are commonly used across different UPS manufacturers based on NUT
 * (Network UPS Tools) analysis.
 */
class GenericHidProtocol : public UpsProtocolBase {
public:
    explicit GenericHidProtocol(UpsHidComponent* parent) : UpsProtocolBase(parent) {}
    ~GenericHidProtocol() override = default;

    // Protocol identification
    DeviceInfo::DetectedProtocol get_protocol_type() const override { 
        return DeviceInfo::PROTOCOL_GENERIC_HID; 
    }
    std::string get_protocol_name() const override { 
        return "Generic HID"; 
    }

    // Core protocol interface
    bool detect() override;
    bool initialize() override;
    bool read_data(UpsData &data) override;
    
    // Delay configuration methods
    bool set_shutdown_delay(int seconds) override;
    bool set_start_delay(int seconds) override;
    bool set_reboot_delay(int seconds) override;

    // Report discovery and enumeration
    void enumerate_reports();
    bool read_report(uint8_t report_id, uint8_t* buffer, size_t& buffer_len);

    // Data parsing methods for different report types
    void parse_power_summary(uint8_t* data, size_t len, UpsData& ups_data);
    void parse_battery_status(uint8_t* data, size_t len, UpsData& ups_data);
    void parse_present_status(uint8_t* data, size_t len, UpsData& ups_data);
    void parse_general_status(uint8_t* data, size_t len, UpsData& ups_data);
    void parse_voltage(uint8_t* data, size_t len, UpsData& ups_data, bool is_input);
    void parse_input_sensitivity(uint8_t* data, size_t len, UpsData& ups_data, const char* style);
    bool parse_unknown_report(uint8_t* data, size_t len, UpsData& ups_data);
    
    // Frequency reading methods
    void read_frequency_data(UpsData &data);
    float parse_frequency_from_report(uint8_t* data, size_t len);
    
    // Configuration reading methods
    void read_delay_configuration(UpsData &data);
    void read_beeper_status(UpsData &data);
    void read_load_percentage(UpsData &data);

    // Test control methods (generic implementations)
    bool start_battery_test_quick() override;
    bool start_battery_test_deep() override;
    bool stop_battery_test() override;
    bool start_ups_test() override;
    bool stop_ups_test() override;

    // Beeper control - not implemented for generic protocol
    bool beeper_enable() override { return false; }
    bool beeper_disable() override { return false; }
    bool beeper_mute() override { return false; }
    bool beeper_test() override { return false; }

private:
    // Report discovery state
    std::set<uint8_t> available_input_reports_;
    std::set<uint8_t> available_feature_reports_;
    std::map<uint8_t, size_t> report_sizes_;
};

} // namespace ups_hid  
} // namespace esphome