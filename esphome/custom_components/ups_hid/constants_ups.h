#pragma once

#include <cstdint>

namespace esphome {
namespace ups_hid {

// ==================== Timing Constants ====================
namespace timing {
    static constexpr uint32_t USB_INITIALIZATION_DELAY_MS = 100;
    static constexpr uint32_t REPORT_RETRY_DELAY_MS = 50;
    static constexpr uint32_t REPORT_DISCOVERY_DELAY_MS = 5;
    static constexpr uint32_t EXTENDED_DISCOVERY_DELAY_MS = 10;
    static constexpr uint32_t PROTOCOL_DETECTION_DELAY_MS = 100;
    
    static constexpr uint32_t MIN_PROTOCOL_TIMEOUT_MS = 5000;      // 5 seconds
    static constexpr uint32_t MAX_PROTOCOL_TIMEOUT_MS = 300000;    // 5 minutes
    static constexpr uint32_t DEFAULT_HID_TIMEOUT_MS = 1000;       // 1 second
    
    static constexpr uint32_t ERROR_RATE_LIMIT_WINDOW_MS = 5000;   // 5 seconds
    static constexpr uint32_t MAX_ERRORS_PER_WINDOW = 3;
    
    // USB operation timeouts
    static constexpr uint32_t USB_CONTROL_TRANSFER_TIMEOUT_MS = 1000;  // 1 second
    static constexpr uint32_t USB_SEMAPHORE_TIMEOUT_MS = 1000;         // 1 second  
    static constexpr uint32_t USB_CLIENT_EVENT_TIMEOUT_MS = 100;       // 100ms for event polling
}

// ==================== Protocol Limits ====================
namespace limits {
    static constexpr uint32_t MAX_CONSECUTIVE_FAILURES = 5;
    static constexpr uint32_t MAX_PROTOCOL_DETECTION_ATTEMPTS = 3;
    static constexpr uint32_t MAX_DISCOVERY_ATTEMPTS = 3;
    static constexpr uint32_t MAX_EXTENDED_DISCOVERY_ATTEMPTS = 10;
    
    static constexpr size_t MAX_HID_REPORT_SIZE = 64;
    static constexpr size_t MIN_HID_REPORT_SIZE = 8;
    static constexpr size_t USB_STRING_DESCRIPTOR_MAX_LENGTH = 256;
}

// ==================== Battery Constants ====================
namespace battery {
    static constexpr float LOW_THRESHOLD_PERCENT = 10.0f;
    static constexpr float MAX_LEVEL_PERCENT = 100.0f;
    static constexpr float VOLTAGE_SCALE_FACTOR = 10.0f;
    static constexpr float ALTERNATIVE_PERCENTAGE_SCALE = 200.0f;
}

// ==================== Voltage Constants ====================
namespace voltage {
    static constexpr float MIN_VALID_VOLTAGE = 80.0f;
    static constexpr float MAX_VALID_VOLTAGE = 300.0f;
    static constexpr float EUROPEAN_STANDARD_VOLTAGE = 230.0f;
    static constexpr float AMERICAN_STANDARD_VOLTAGE = 120.0f;
}

// ==================== Default Timer Values ====================
namespace defaults {
    static constexpr int CYBERPOWER_SHUTDOWN_DELAY_SEC = 60;
    static constexpr int CYBERPOWER_STARTUP_DELAY_SEC = 120;
    static constexpr int REBOOT_TIMER_DEFAULT = -10;
    static constexpr uint16_t AUTO_DETECT_VENDOR_ID = 0;
    static constexpr uint16_t AUTO_DETECT_PRODUCT_ID = 0;
}

// ==================== Status Strings ====================
namespace status {
    static constexpr const char* ONLINE = "Online";
    static constexpr const char* ON_BATTERY = "On Battery";
    static constexpr const char* UNKNOWN = "Unknown";
    static constexpr const char* CONNECTED = "Connected";
    static constexpr const char* DISCONNECTED = "Disconnected";
    static constexpr const char* DETECTION_PENDING = "Detection pending";
    static constexpr const char* NONE = "None";
    static constexpr const char* YES = "YES";
    static constexpr const char* NO = "NO";
}

// ==================== Battery Status Strings ====================
namespace battery_status {
    static constexpr const char* CHARGING = "Charging";
    static constexpr const char* DISCHARGING = "Discharging";
    static constexpr const char* FULLY_CHARGED = "Fully Charged";
    static constexpr const char* NOT_CHARGING = "Not Charging";
    static constexpr const char* NORMAL = "Normal";
    static constexpr const char* FULL = "Full";
    static constexpr const char* GOOD = "Good";
    static constexpr const char* LOW = "Low";
    static constexpr const char* CRITICAL = "Critical";
    static constexpr const char* NOT_PRESENT = "Not Present";
    static constexpr const char* FAULT = "Fault";
    static constexpr const char* UNKNOWN = "Unknown";
    
    // Battery status suffixes (append to base status)
    static constexpr const char* TIME_LIMIT_EXPIRED_SUFFIX = " - Time Limit Expired";
    static constexpr const char* REPLACE_BATTERY_SUFFIX = " - Replace Battery";
    static constexpr const char* INTERNAL_FAILURE_SUFFIX = " - Internal Failure";
    static constexpr const char* CHECK_BATTERY_SUFFIX = " - Check Battery";
    static constexpr const char* SHUTDOWN_IMMINENT_SUFFIX = " - Shutdown Imminent";
    static constexpr const char* FAULT_SUFFIX = " - Fault";
}

// ==================== Battery Chemistry Types ====================
namespace battery_chemistry {
    static constexpr const char* ALKALINE = "Alkaline";          // Chemistry code 1
    static constexpr const char* NICD = "NiCd";                  // Chemistry code 2
    static constexpr const char* NIMH = "NiMH";                  // Chemistry code 3
    static constexpr const char* LEAD_ACID = "PbAcid";           // Chemistry code 4 (NUT standard)
    static constexpr const char* LITHIUM_ION = "LiIon";         // Chemistry code 5
    static constexpr const char* LITHIUM_POLYMER = "LiPoly";    // Chemistry code 6
    static constexpr const char* UNKNOWN = battery_status::UNKNOWN;
    
    // Common HID report ID for battery chemistry (used by both APC and CyberPower)
    static constexpr uint8_t REPORT_ID = 0x03;
    
    // Chemistry ID constants (HID standard values)
    static constexpr uint8_t ID_ALKALINE = 1;
    static constexpr uint8_t ID_NICD = 2;
    static constexpr uint8_t ID_NIMH = 3;
    static constexpr uint8_t ID_LEAD_ACID = 4;
    static constexpr uint8_t ID_LITHIUM_ION = 5;
    static constexpr uint8_t ID_LITHIUM_POLYMER = 6;
    
    // Helper function to convert chemistry ID to string
    inline const char* id_to_string(uint8_t chemistry_id) {
        switch (chemistry_id) {
            case ID_ALKALINE: return ALKALINE;
            case ID_NICD: return NICD;
            case ID_NIMH: return NIMH;
            case ID_LEAD_ACID: return LEAD_ACID;
            case ID_LITHIUM_ION: return LITHIUM_ION;
            case ID_LITHIUM_POLYMER: return LITHIUM_POLYMER;
            default: return UNKNOWN;
        }
    }
}

// ==================== Beeper Actions ====================
namespace beeper {
    static constexpr const char* ACTION_ENABLE = "enable";
    static constexpr const char* ACTION_DISABLE = "disable";
    static constexpr const char* ACTION_MUTE = "mute";
    static constexpr const char* ACTION_TEST = "test";
    
    // Beeper control values
    static constexpr uint8_t CONTROL_DISABLE = 0x01;
    static constexpr uint8_t CONTROL_ENABLE = 0x02;
    static constexpr uint8_t CONTROL_MUTE = 0x03;
}

// ==================== Test Actions ====================
namespace test {
    static constexpr const char* ACTION_BATTERY_QUICK = "battery_quick";
    static constexpr const char* ACTION_BATTERY_DEEP = "battery_deep";
    static constexpr const char* ACTION_BATTERY_STOP = "battery_stop";
    static constexpr const char* ACTION_UPS_TEST = "ups_test";
    static constexpr const char* ACTION_UPS_STOP = "ups_stop";
    
    // Test command values
    static constexpr uint8_t COMMAND_QUICK = 1;
    static constexpr uint8_t COMMAND_DEEP = 2;
    static constexpr uint8_t COMMAND_ABORT = 3;
    
    // Test result status strings (shared by APC and CyberPower)
    static constexpr const char* RESULT_DONE_PASSED = "Done and passed";
    static constexpr const char* RESULT_DONE_WARNING = "Done and warning";
    static constexpr const char* RESULT_DONE_ERROR = "Done and error";
    static constexpr const char* RESULT_ABORTED = "Aborted";
    static constexpr const char* RESULT_IN_PROGRESS = "In progress";
    static constexpr const char* RESULT_NO_TEST = "No test initiated";
    static constexpr const char* RESULT_SCHEDULED = "Test scheduled";
    static constexpr const char* RESULT_ERROR_READING = "Error reading test result";
}

// ==================== Sensor Type Identifiers ====================
namespace sensor_type {
    static constexpr const char* BATTERY_LEVEL = "battery_level";
    static constexpr const char* BATTERY_VOLTAGE = "battery_voltage";
    static constexpr const char* BATTERY_VOLTAGE_NOMINAL = "battery_voltage_nominal";
    static constexpr const char* RUNTIME = "runtime";
    static constexpr const char* INPUT_VOLTAGE = "input_voltage";
    static constexpr const char* INPUT_VOLTAGE_NOMINAL = "input_voltage_nominal";
    static constexpr const char* OUTPUT_VOLTAGE = "output_voltage";
    static constexpr const char* LOAD_PERCENT = "load_percent";
    static constexpr const char* FREQUENCY = "frequency";
    static constexpr const char* INPUT_TRANSFER_LOW = "input_transfer_low";
    static constexpr const char* INPUT_TRANSFER_HIGH = "input_transfer_high";
    static constexpr const char* BATTERY_RUNTIME_LOW = "battery_runtime_low";
    static constexpr const char* UPS_REALPOWER_NOMINAL = "ups_realpower_nominal";
    static constexpr const char* UPS_DELAY_SHUTDOWN = "ups_delay_shutdown";
    static constexpr const char* UPS_DELAY_START = "ups_delay_start";
    static constexpr const char* UPS_DELAY_REBOOT = "ups_delay_reboot";
    static constexpr const char* UPS_TIMER_REBOOT = "ups_timer_reboot";
    static constexpr const char* UPS_TIMER_SHUTDOWN = "ups_timer_shutdown";
    static constexpr const char* UPS_TIMER_START = "ups_timer_start";
    static constexpr const char* TEMPERATURE = "ups_temperature";
}

// ==================== Binary Sensor Type Identifiers ====================
namespace binary_sensor_type {
    static constexpr const char* ONLINE = "online";
    static constexpr const char* ON_BATTERY = "on_battery";
    static constexpr const char* LOW_BATTERY = "low_battery";
    static constexpr const char* OVERLOAD = "overload";
    static constexpr const char* BUCK = "buck";
    static constexpr const char* BOOST = "boost";
    static constexpr const char* CHARGING = "charging";
    static constexpr const char* DISCHARGING = "discharging";
    static constexpr const char* BYPASS_ACTIVE = "bypass_active";
}

// ==================== Text Sensor Type Identifiers ====================
namespace text_sensor_type {
    static constexpr const char* MODEL = "model";
    static constexpr const char* MANUFACTURER = "manufacturer";
    static constexpr const char* SERIAL_NUMBER = "serial_number";
    static constexpr const char* FIRMWARE_VERSION = "firmware_version";
    static constexpr const char* BATTERY_STATUS = "battery_status";
    static constexpr const char* UPS_TEST_RESULT = "ups_test_result";
    static constexpr const char* UPS_BEEPER_STATUS = "ups_beeper_status";
    static constexpr const char* INPUT_SENSITIVITY = "input_sensitivity";
    static constexpr const char* STATUS = "status";
    static constexpr const char* PROTOCOL = "protocol";
    static constexpr const char* BATTERY_MFR_DATE = "battery_mfr_date";
    static constexpr const char* UPS_MFR_DATE = "ups_mfr_date";
    static constexpr const char* BATTERY_TYPE = "battery_type";
    static constexpr const char* UPS_FIRMWARE_AUX = "ups_firmware_aux";
    // Standard NUT ups.status format: space-separated codes like "OL",
    // "OB CHRG", "OB DISCHRG LB", "OL ALARM", etc. - the same string a
    // real `upsc` client would see. Distinct from STATUS above, which is
    // free-form human text ("Online", "On Battery"...).
    static constexpr const char* NUT_STATUS = "nut_status";
}

// ==================== Input Sensitivity Values ====================
namespace sensitivity {
    static constexpr const char* HIGH = "high";
    static constexpr const char* NORMAL = "normal";
    static constexpr const char* LOW = "low";
    static constexpr const char* AUTO = "auto";
    static constexpr const char* UNKNOWN = "unknown";
}

// ==================== Protocol Names ====================
namespace protocol {
    static constexpr const char* APC_HID = "APC HID";
    static constexpr const char* CYBERPOWER = "CyberPower";
    static constexpr const char* GENERIC = "Generic";
    static constexpr const char* NONE = "None";
}

// ==================== USB/HID Constants ====================
namespace usb {
    // Common vendor IDs
    static constexpr uint16_t VENDOR_ID_APC = 0x051D;
    static constexpr uint16_t VENDOR_ID_CYBERPOWER = 0x0764;
    // Cypress Semiconductor USB-to-serial bridge, used by many "Megatec/Q1"
    // offline/line-interactive UPS units (Ippon, several other rebadged
    // Chinese UPS designs). Confirmed via NUT's blazer_usb "cypress"
    // subdriver (vendorid=0665). Not exclusive to Megatec devices in
    // general, but consistently correct for this specific chip family.
    static constexpr uint16_t VENDOR_ID_CYPRESS_MEGATEC = 0x0665;
    
    // Common product IDs
    static constexpr uint16_t PRODUCT_ID_APC_BACK_UPS_ES_700 = 0x0002; // Back-UPS ES 700G (INPUT-ONLY)
    
    // Common HID report IDs used across multiple UPS vendors
    static constexpr uint8_t REPORT_ID_SERIAL_NUMBER = 0x02;  // Serial number string descriptor index
}

// ==================== Log Messages ====================
namespace log_messages {
    static constexpr const char* SETTING_UP = "Setting up UPS HID Component...";
    static constexpr const char* TRANSPORT_INIT_FAILED = "Failed to initialize transport";
    static constexpr const char* SETUP_COMPLETE = "UPS HID Component setup complete - waiting for USB device connection";
    static constexpr const char* WAITING_FOR_DEVICE = "USB transport not connected - waiting for device";
    static constexpr const char* ATTEMPTING_DETECTION = "USB device connected - attempting protocol detection";
    static constexpr const char* PROTOCOL_DETECTED = "UPS protocol detected and configured successfully";
    static constexpr const char* DETECTION_FAILED = "Failed to detect UPS protocol (attempt #%u)";
    static constexpr const char* TOO_MANY_FAILURES = "Too many consecutive protocol detection failures, marking component as failed";
    static constexpr const char* READ_FAILED = "Failed to read UPS data (failure #%u)";
    static constexpr const char* RESETTING_PROTOCOL = "Too many consecutive read failures - resetting protocol to retry detection";
    static constexpr const char* NO_PARENT_COMPONENT = "No UPS HID parent component set";
}

}  // namespace ups_hid
}  // namespace esphome