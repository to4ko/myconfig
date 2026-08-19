#pragma once

#include "transport_interface.h"
#include <map>
#include <chrono>

namespace esphome {
namespace ups_hid {

/**
 * Simulated USB Transport Implementation
 * 
 * Provides realistic UPS data simulation for testing and development
 * without requiring physical hardware
 */
class SimulatedTransport : public IUsbTransport {
public:
    SimulatedTransport();
    ~SimulatedTransport() override = default;
    
    // IUsbTransport implementation
    esp_err_t initialize() override;
    esp_err_t deinitialize() override;
    
    bool is_connected() const override;
    uint16_t get_vendor_id() const override;
    uint16_t get_product_id() const override;
    
    esp_err_t hid_get_report(uint8_t report_type, uint8_t report_id, 
                           uint8_t* data, size_t* data_len, 
                           uint32_t timeout_ms = 1000) override;
    
    esp_err_t hid_set_report(uint8_t report_type, uint8_t report_id,
                           const uint8_t* data, size_t data_len,
                           uint32_t timeout_ms = 1000) override;

    esp_err_t hid_interrupt_read(uint8_t* data, size_t* data_len,
                               uint32_t timeout_ms = 1000) override;
    
    esp_err_t get_string_descriptor(uint8_t string_index, 
                                  std::string& result) override;
    
    std::string get_last_error() const override;

private:
    bool connected_{false};
    bool initialized_{false};
    uint16_t vendor_id_{0x051D}; // Default to APC
    uint16_t product_id_{0x0002}; // APC Back-UPS ES
    std::string last_error_;
    
    // Simulation state
    std::chrono::steady_clock::time_point start_time_;
    float battery_level_{85.0f};
    float input_voltage_{120.0f};
    float output_voltage_{120.0f};
    float load_percent_{25.0f};
    uint16_t runtime_minutes_{45};
    std::string beeper_status_{"enabled"};
    std::string test_result_{"No test initiated"};
    bool test_running_{false};
    
    // Simulated report generation
    void generate_battery_report(uint8_t report_id, uint8_t* data, size_t* data_len);
    void generate_power_report(uint8_t report_id, uint8_t* data, size_t* data_len);
    void generate_status_report(uint8_t report_id, uint8_t* data, size_t* data_len);
    void generate_beeper_report(uint8_t report_id, uint8_t* data, size_t* data_len);
    void generate_test_report(uint8_t report_id, uint8_t* data, size_t* data_len);
    void generate_device_info_report(uint8_t report_id, uint8_t* data, size_t* data_len);
    
    // Dynamic data simulation
    void update_simulation_data();
    float get_elapsed_seconds() const;
};

} // namespace ups_hid
} // namespace esphome