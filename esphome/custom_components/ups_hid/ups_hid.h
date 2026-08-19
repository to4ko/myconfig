#pragma once

#include "esphome/core/component.h"
#include "esphome/core/defines.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

// Forward declarations for optional sensor platforms
#ifdef USE_SENSOR
#include "sensor_numeric.h"
namespace esphome { namespace sensor { class Sensor; } }
#endif

#ifdef USE_BINARY_SENSOR  
#include "sensor_binary.h"
namespace esphome { namespace binary_sensor { class BinarySensor; } }
#endif

#ifdef USE_TEXT_SENSOR
#include "sensor_text.h" 
namespace esphome { namespace text_sensor { class TextSensor; } }
#endif

#include <memory>
#include <vector>
#include <unordered_map>
#include <string>
#include <mutex>

#ifdef USE_ESP32
#include "esp_err.h"
#include "usb/usb_host.h"
#include "usb/usb_types_ch9.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "freertos/portmacro.h"
#include "driver/gpio.h"
#include <set>
#include <map>

// USB HID Class defines
// USB HID Class constant is now defined in hid_constants.h

#endif

// Include the clean refactored architecture
#include "data_composite.h"
#include "transport_interface.h"
#include "protocol_factory.h"
#include "constants_hid.h"

namespace esphome
{
  namespace ups_hid
  {

    static const char *const TAG = "ups_hid";
    
    // Forward declarations
    class UpsProtocolBase;
    class IUsbTransport;

    class UpsHidComponent : public PollingComponent
    {
    public:
      UpsHidComponent() = default;
      ~UpsHidComponent() = default;

      void setup() override;
      void update() override;
      void dump_config() override;
      float get_setup_priority() const override { return setup_priority::DATA; }

      // Configuration setters with validation
      void set_simulation_mode(bool simulation_mode) { simulation_mode_ = simulation_mode; }
      void set_usb_vendor_id(uint16_t vendor_id) { 
        usb_vendor_id_ = vendor_id; 
      }
      void set_usb_product_id(uint16_t product_id) { 
        usb_product_id_ = product_id; 
      }
      void set_protocol_timeout(uint32_t timeout_ms) { 
        // Bound timeout between 5 seconds and 5 minutes for safety
        protocol_timeout_ms_ = std::max(static_cast<uint32_t>(5000), 
                                       std::min(timeout_ms, static_cast<uint32_t>(300000)));
      }
      void set_protocol_selection(const std::string &protocol) { protocol_selection_ = protocol; }
      void set_fallback_nominal_voltage(float voltage) { fallback_nominal_voltage_ = voltage; }

      // Data getters for sensors (thread-safe)
      UpsData get_ups_data() const { 
        std::lock_guard<std::mutex> lock(data_mutex_);
        return ups_data_; 
      }
      std::string get_protocol_name() const;
      uint32_t get_protocol_timeout() const { return protocol_timeout_ms_; }
      float get_fallback_nominal_voltage() const { return fallback_nominal_voltage_; }
      
      // Convenient state getters for lambda expressions (no sensor entities required)
      bool is_online() const;
      bool is_on_battery() const;  
      bool is_low_battery() const;
      bool is_charging() const;
      bool has_fault() const;
      bool is_overloaded() const;
      // Standard NUT ups.status string (e.g. "OL", "OB CHRG", "OB DISCHRG
      // LB", "OL ALARM") built from the flags above - the same logic
      // nut_server uses to answer real NUT clients, exposed here too so it
      // can be shown as a plain ESPHome text sensor without needing a
      // separate NUT integration in Home Assistant.
      std::string get_nut_status() const;
      float get_battery_level() const;
      float get_input_voltage() const;
      float get_output_voltage() const;
      float get_load_percent() const;
      float get_runtime_minutes() const;
      
      // Test control methods
      bool start_battery_test_quick();
      bool start_battery_test_deep();
      bool stop_battery_test();
      bool start_ups_test();
      bool stop_ups_test();
      
      // Beeper control methods
      bool beeper_enable();
      bool beeper_disable();
      bool beeper_mute();
      bool beeper_test();
      
      // Delay configuration methods
      bool set_shutdown_delay(int seconds);
      bool set_start_delay(int seconds);
      bool set_reboot_delay(int seconds);
      void request_delay_refresh() { /* No-op for now - could trigger update if needed */ }

      // Sensor registration methods (conditional on platform availability)
#ifdef USE_SENSOR      
      void register_sensor(sensor::Sensor *sens, const std::string &type);
#endif
#ifdef USE_BINARY_SENSOR
      void register_binary_sensor(binary_sensor::BinarySensor *sens, const std::string &type);
#endif
#ifdef USE_TEXT_SENSOR
      void register_text_sensor(text_sensor::TextSensor *sens, const std::string &type);
#endif
      void register_delay_number(class UpsDelayNumber *number);
      
      // Protocol access for button components
      UpsProtocolBase* get_active_protocol() const { return active_protocol_.get(); }

    protected:
      bool simulation_mode_{false};
      uint16_t usb_vendor_id_{0};  // 0 means auto-detect
      uint16_t usb_product_id_{0}; // 0 means auto-detect
      uint32_t protocol_timeout_ms_{10000};
      std::string protocol_selection_{"auto"};
      float fallback_nominal_voltage_{230.0f};  // European standard (230V) for international compatibility

      bool connected_{false};
      uint32_t last_successful_read_{0};
      uint32_t consecutive_failures_{0};
      uint32_t max_consecutive_failures_{5};  // Limit re-detection attempts
      UpsData ups_data_;
      mutable std::mutex data_mutex_;  // Protect ups_data_ access
      
      // Fast polling for timer countdown
      bool fast_polling_mode_{false};
      uint32_t last_timer_poll_{0};
      static constexpr uint32_t FAST_POLL_INTERVAL_MS = 2000;  // 2 seconds during countdown
      
      // Error rate limiting to prevent log spam
      struct ErrorRateLimit {
        uint32_t last_error_time{0};
        uint32_t error_count{0};
        uint32_t suppressed_count{0};
        static constexpr uint32_t RATE_LIMIT_MS = 5000;  // 5 seconds between repeated errors
        static constexpr uint32_t MAX_BURST = 3;         // Allow 3 errors before rate limiting
      };
      ErrorRateLimit usb_error_limiter_;
      ErrorRateLimit protocol_error_limiter_;

      // Clean architecture members
      std::unique_ptr<IUsbTransport> transport_;
      std::unique_ptr<UpsProtocolBase> active_protocol_;
      
      // Sensor storage (conditional on platform availability)
#ifdef USE_SENSOR      
      std::unordered_map<std::string, sensor::Sensor *> sensors_;
#endif
#ifdef USE_BINARY_SENSOR
      std::unordered_map<std::string, binary_sensor::BinarySensor *> binary_sensors_;
#endif
#ifdef USE_TEXT_SENSOR
      std::unordered_map<std::string, text_sensor::TextSensor *> text_sensors_;
#endif
      std::vector<class UpsDelayNumber *> delay_numbers_;

      // Core methods
      bool initialize_transport();
      bool detect_protocol();
      bool read_ups_data();
      void update_sensors();
      
      // Timer polling methods
      void check_and_update_timers();
      bool has_active_timers() const;
      void set_fast_polling_mode(bool enable);
      
      // Error rate limiting helpers
      bool should_log_error(ErrorRateLimit& limiter);
      void log_suppressed_errors(ErrorRateLimit& limiter);

    public:
      // Transport abstraction methods (accessible by protocol classes)
      esp_err_t hid_get_report(uint8_t report_type, uint8_t report_id, 
                             uint8_t* data, size_t* data_len, 
                             uint32_t timeout_ms = 1000);
      esp_err_t hid_set_report(uint8_t report_type, uint8_t report_id,
                             const uint8_t* data, size_t data_len,
                             uint32_t timeout_ms = 1000);
      esp_err_t hid_interrupt_read(uint8_t* data, size_t* data_len,
                             uint32_t timeout_ms = 1000);
      esp_err_t get_string_descriptor(uint8_t string_index, std::string& result);
      
      // Transport information
      bool is_connected() const;
      uint16_t get_vendor_id() const; 
      uint16_t get_product_id() const;
      
      // Legacy compatibility for protocols
      bool is_device_connected() const { return is_connected(); }
      esp_err_t usb_get_string_descriptor(uint8_t string_index, std::string& result) {
        return get_string_descriptor(string_index, result);
      }
      

    private:
      // Internal helper methods
      void cleanup();

      // Lock-free counterparts of is_online()/is_on_battery()/
      // is_low_battery()/is_charging()/has_fault()/get_nut_status(),
      // for use by code that already holds data_mutex_ (namely
      // update_sensors()). The public versions above just lock and
      // delegate to these - calling the public (locking) versions from
      // inside update_sensors() would deadlock, since std::mutex isn't
      // reentrant.
      bool is_online_locked() const;
      bool is_on_battery_locked() const;
      bool is_low_battery_locked() const;
      bool is_charging_locked() const;
      bool has_fault_locked() const;
      std::string get_nut_status_locked() const;
    };

    // Base class for UPS protocols
    class UpsProtocolBase
    {
    public:
      explicit UpsProtocolBase(UpsHidComponent *parent) : parent_(parent) {}
      virtual ~UpsProtocolBase() = default;

      virtual bool detect() = 0;
      virtual bool initialize() = 0;
      virtual bool read_data(UpsData &data) = 0;
      virtual DeviceInfo::DetectedProtocol get_protocol_type() const = 0;
      virtual std::string get_protocol_name() const = 0;
      
      // Beeper control methods
      virtual bool beeper_enable() { return false; }
      virtual bool beeper_disable() { return false; }
      virtual bool beeper_mute() { return false; }
      virtual bool beeper_test() { return false; }
      
      // UPS and battery test methods
      virtual bool start_battery_test_quick() { return false; }
      virtual bool start_battery_test_deep() { return false; }
      virtual bool stop_battery_test() { return false; }
      virtual bool start_ups_test() { return false; }
      virtual bool stop_ups_test() { return false; }
      
      // Timer polling method for real-time countdown
      virtual bool read_timer_data(UpsData &data) { return false; }
      
      // Delay configuration methods
      virtual bool set_shutdown_delay(int seconds) { return false; }
      virtual bool set_start_delay(int seconds) { return false; }
      virtual bool set_reboot_delay(int seconds) { return false; }

    protected:
      UpsHidComponent *parent_;

      bool send_command(const std::vector<uint8_t> &cmd, std::vector<uint8_t> &response, uint32_t timeout_ms = 1000);
      std::string bytes_to_string(const std::vector<uint8_t> &data);
    };


  } // namespace ups_hid
} // namespace esphome