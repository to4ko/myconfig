#pragma once

/**
 * @file hid_constants.h  
 * @brief HID Constants for UPS Power Device Class
 * 
 * Standard USB HID constants following USB HID Usage Tables v1.6
 * and USB Device Class Definition for HID Power Devices v1.1
 * 
 * References:
 * - USB HID Usage Tables v1.6: https://usb.org/document-library/hid-usage-tables-16
 * - USB Power Device Class v1.1: https://usb.org/sites/default/files/pdcv11.pdf
 * - NUT HID Implementation: drivers/hidtypes.h
 */

// =============================================================================
// USB HID Class and Report Types (USB HID Specification v1.11)
// =============================================================================

#define USB_CLASS_HID                   0x03

#define HID_REPORT_TYPE_INPUT           0x01
#define HID_REPORT_TYPE_OUTPUT          0x02  
#define HID_REPORT_TYPE_FEATURE         0x03

// =============================================================================
// HID Usage Pages (USB HID Usage Tables v1.12)
// =============================================================================

#define HID_USAGE_PAGE_POWER_DEVICE     0x84
#define HID_USAGE_PAGE_BATTERY_SYSTEM   0x85

// =============================================================================
// Power Device Usage IDs (HID Power Device Class v1.1)
// =============================================================================

// Device Identification
#define HID_USAGE_POW_I_NAME                    0x0001
#define HID_USAGE_POW_PRESENT_STATUS            0x0002
#define HID_USAGE_POW_UPS                       0x0004
#define HID_USAGE_POW_POWER_SUPPLY              0x0005

// Power Components
#define HID_USAGE_POW_BATTERY_SYSTEM            0x0010
#define HID_USAGE_POW_BATTERY                   0x0012
#define HID_USAGE_POW_INPUT                     0x001A
#define HID_USAGE_POW_OUTPUT                    0x001C
#define HID_USAGE_POW_POWER_SUMMARY             0x0024

// Measurements
#define HID_USAGE_POW_VOLTAGE                   0x0030
#define HID_USAGE_POW_CURRENT                   0x0031
#define HID_USAGE_POW_FREQUENCY                 0x0032
#define HID_USAGE_POW_APPARENT_POWER            0x0033
#define HID_USAGE_POW_ACTIVE_POWER              0x0034
#define HID_USAGE_POW_PERCENT_LOAD              0x0035
#define HID_USAGE_POW_TEMPERATURE               0x0036

// Configuration Values (Nominal/Reference)
#define HID_USAGE_POW_CONFIG_VOLTAGE            0x0040
#define HID_USAGE_POW_CONFIG_CURRENT            0x0041
#define HID_USAGE_POW_CONFIG_FREQUENCY          0x0042
#define HID_USAGE_POW_CONFIG_APPARENT_POWER     0x0043
#define HID_USAGE_POW_CONFIG_ACTIVE_POWER       0x0044
#define HID_USAGE_POW_CONFIG_PERCENT_LOAD       0x0045

// Control Operations
#define HID_USAGE_POW_SWITCH_ON_CONTROL         0x0050
#define HID_USAGE_POW_SWITCH_OFF_CONTROL        0x0051
#define HID_USAGE_POW_LOW_VOLTAGE_TRANSFER      0x0053
#define HID_USAGE_POW_HIGH_VOLTAGE_TRANSFER     0x0054
#define HID_USAGE_POW_DELAY_BEFORE_REBOOT       0x0055
#define HID_USAGE_POW_DELAY_BEFORE_STARTUP      0x0056
#define HID_USAGE_POW_DELAY_BEFORE_SHUTDOWN     0x0057
#define HID_USAGE_POW_TEST                      0x0058
#define HID_USAGE_POW_AUDIBLE_ALARM_CONTROL     0x005A

// Status Indicators  
#define HID_USAGE_POW_PRESENT                   0x0060
#define HID_USAGE_POW_GOOD                      0x0061
#define HID_USAGE_POW_INTERNAL_FAILURE          0x0062
#define HID_USAGE_POW_VOLTAGE_OUT_OF_RANGE      0x0063
#define HID_USAGE_POW_OVERLOAD                  0x0065
#define HID_USAGE_POW_OVER_CHARGED              0x0066
#define HID_USAGE_POW_SHUTDOWN_REQUESTED        0x0068
#define HID_USAGE_POW_SHUTDOWN_IMMINENT         0x0069

// Device Information
#define HID_USAGE_POW_I_MANUFACTURER            0x00FD
#define HID_USAGE_POW_I_PRODUCT                 0x00FE
#define HID_USAGE_POW_I_SERIAL_NUMBER           0x00FF

// =============================================================================
// Battery System Usage IDs (HID Power Device Class v1.1)
// =============================================================================

// Battery Status
#define HID_USAGE_BAT_CHARGING                  0x0044
#define HID_USAGE_BAT_DISCHARGING               0x0045
#define HID_USAGE_BAT_FULLY_CHARGED             0x0046
#define HID_USAGE_BAT_NEED_REPLACEMENT          0x004B

// Battery Measurements
#define HID_USAGE_BAT_REMAINING_CAPACITY        0x0066
#define HID_USAGE_BAT_FULL_CHARGE_CAPACITY      0x0067
#define HID_USAGE_BAT_RUN_TIME_TO_EMPTY         0x0068
#define HID_USAGE_BAT_AVERAGE_TIME_TO_EMPTY     0x0069
#define HID_USAGE_BAT_AVERAGE_TIME_TO_FULL      0x006A

// Battery Configuration
#define HID_USAGE_BAT_DESIGN_CAPACITY           0x0083
#define HID_USAGE_BAT_WARNING_CAPACITY_LIMIT    0x008C

// Battery Information
#define HID_USAGE_BAT_I_MANUFACTURER_NAME       0x0087
#define HID_USAGE_BAT_I_DEVICE_NAME             0x0088
#define HID_USAGE_BAT_I_DEVICE_CHEMISTRY        0x0089

// =============================================================================
// Regional Voltage Standards (IEC 60038)
// =============================================================================

// Single-phase nominal voltages (RMS)
#define VOLTAGE_NOMINAL_EU                      230.0f    // Europe (IEC 60038)
#define VOLTAGE_NOMINAL_US                      120.0f    // North America  
#define VOLTAGE_NOMINAL_JP                      100.0f    // Japan
#define VOLTAGE_NOMINAL_UK                      230.0f    // United Kingdom
#define VOLTAGE_NOMINAL_AU                      230.0f    // Australia

// Voltage tolerance ranges (±10% typical)
#define VOLTAGE_MIN_VALID                       80.0f     // Minimum valid voltage
#define VOLTAGE_MAX_VALID                       300.0f    // Maximum valid voltage

// Three-phase nominal voltages (for industrial UPS)
#define VOLTAGE_NOMINAL_3P_EU                   400.0f    // Europe 3-phase
#define VOLTAGE_NOMINAL_3P_US                   208.0f    // North America 3-phase

// =============================================================================
// Regional Frequency Standards (IEC 60038)
// =============================================================================

// Standard AC frequencies (Hz)
#define FREQUENCY_NOMINAL_EU                    50.0f     // Europe (IEC 60038)
#define FREQUENCY_NOMINAL_US                    60.0f     // North America
#define FREQUENCY_NOMINAL_JP                    50.0f     // Japan (50Hz East, 60Hz West)
#define FREQUENCY_NOMINAL_UK                    50.0f     // United Kingdom
#define FREQUENCY_NOMINAL_AU                    50.0f     // Australia

// Frequency tolerance ranges (typical ±1% for power systems)
#define FREQUENCY_MIN_VALID                     47.0f     // Minimum valid frequency (50Hz -6%)
#define FREQUENCY_MAX_VALID                     65.0f     // Maximum valid frequency (60Hz +8%)

// Specialized frequency applications  
#define FREQUENCY_AIRCRAFT                      400.0f    // Aircraft power systems
#define FREQUENCY_RAILWAY                       16.7f     // Railway power systems (Europe)
#define FREQUENCY_RAILWAY_US                    25.0f     // Railway power systems (North America)

// =============================================================================
// Helper Macros for HID Usage Paths
// =============================================================================

// Create full 32-bit HID usage from page and usage ID
#define HID_USAGE(page, usage)          (((uint32_t)(page) << 16) | (usage))

// Power Device usages
#define HID_USAGE_POW(usage)            HID_USAGE(HID_USAGE_PAGE_POWER_DEVICE, usage)
#define HID_USAGE_BAT(usage)            HID_USAGE(HID_USAGE_PAGE_BATTERY_SYSTEM, usage)

// Common voltage usage paths (for NUT-style path matching)
#define HID_PATH_INPUT_VOLTAGE          HID_USAGE_POW(HID_USAGE_POW_VOLTAGE)
#define HID_PATH_INPUT_CONFIG_VOLTAGE   HID_USAGE_POW(HID_USAGE_POW_CONFIG_VOLTAGE)
#define HID_PATH_OUTPUT_VOLTAGE         HID_USAGE_POW(HID_USAGE_POW_VOLTAGE)
#define HID_PATH_BATTERY_VOLTAGE        HID_USAGE_POW(HID_USAGE_POW_VOLTAGE)