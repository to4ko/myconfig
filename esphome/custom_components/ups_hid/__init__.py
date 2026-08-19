"""UPS HID Component for ESPHome - Enhanced validation and configuration."""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import (
    CONF_ID,
    CONF_UPDATE_INTERVAL,
)

DEPENDENCIES = ["esp32"]
MULTI_CONF = True

CONF_SIMULATION_MODE = "simulation_mode"
CONF_USB_VENDOR_ID = "usb_vendor_id"
CONF_USB_PRODUCT_ID = "usb_product_id"
CONF_PROTOCOL_TIMEOUT = "protocol_timeout"
CONF_PROTOCOL = "protocol"
CONF_FALLBACK_NOMINAL_VOLTAGE = "fallback_nominal_voltage"
CONF_UPS_HID_ID = "ups_hid_id"

# Known UPS vendor IDs for validation
KNOWN_VENDOR_IDS = {
    0x0463: "MGE Office Protection Systems",
    0x047C: "Dell",
    0x0483: "STMicroelectronics",
    0x04B3: "IBM",
    0x04D8: "OpenUPS",
    0x050D: "Belkin",
    0x051D: "APC",
    0x0592: "Powerware",
    0x05DD: "Delta Electronics",
    0x0665: "Cypress Semiconductor (Megatec/Q1, e.g. many Ippon UPS units)",
    0x06DA: "MGE UPS Systems",
    0x075D: "Idowell",
    0x0764: "CyberPower",
    0x09AE: "Tripp Lite",
    0x09D6: "KSTAR",
}

ups_hid_ns = cg.esphome_ns.namespace("ups_hid")
UpsHidComponent = ups_hid_ns.class_("UpsHidComponent", cg.PollingComponent)


def validate_usb_config(config):
    """Validate USB configuration. Manual IDs are now troubleshooting fallbacks only."""
    vendor_id = config.get(CONF_USB_VENDOR_ID)
    product_id = config.get(CONF_USB_PRODUCT_ID)

    # If either ID is specified, both must be provided for troubleshooting mode
    if vendor_id is not None or product_id is not None:
        if vendor_id is None or product_id is None:
            raise cv.Invalid("When using manual USB IDs for troubleshooting, both vendor_id and product_id must be specified")
        
        # Validate non-zero IDs
        if vendor_id == 0 or product_id == 0:
            raise cv.Invalid("USB vendor and product IDs must be non-zero")

        # Warn about unknown vendor IDs
        if vendor_id not in KNOWN_VENDOR_IDS:
            # Just log a warning instead of failing - this is for troubleshooting
            import logging
            logging.getLogger(__name__).warning(
                f"Unknown USB vendor ID 0x{vendor_id:04X}. "
                "Component will attempt auto-detection first, then fall back to manual settings."
            )

    return config


def validate_protocol_timeout(value):
    """Validate protocol timeout with reasonable bounds."""
    value = cv.positive_time_period_milliseconds(value)
    ms = value.total_milliseconds

    if ms < 5000:
        raise cv.Invalid(
            "Protocol timeout must be at least 5 seconds for reliable communication"
        )
    if ms > 60000:
        raise cv.Invalid(
            "Protocol timeout must be at most 60 seconds to avoid blocking"
        )

    return value


def validate_update_interval(value):
    """Validate update interval for UPS HID monitoring."""
    value = cv.update_interval(value)
    ms = value.total_milliseconds

    if ms < 5000:
        cg.global_ns.logger.LOGGER.warning(
            "Update interval less than 5 seconds may cause excessive USB traffic. "
            "Consider using 10s or higher for production."
        )

    return value


def validate_fallback_nominal_voltage(value):
    """Validate fallback nominal voltage for international compatibility."""
    value = cv.voltage(value)
    
    if value < 80.0:
        raise cv.Invalid("Fallback nominal voltage must be at least 80V")
    if value > 300.0:
        raise cv.Invalid("Fallback nominal voltage must be at most 300V")
    
    return value


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(UpsHidComponent),
            cv.Optional(CONF_SIMULATION_MODE, default=False): cv.boolean,
            # Manual USB IDs are now primarily for troubleshooting when auto-detection fails
            cv.Optional(CONF_USB_VENDOR_ID): cv.hex_uint16_t,
            cv.Optional(CONF_USB_PRODUCT_ID): cv.hex_uint16_t,
            cv.Optional(
                CONF_PROTOCOL_TIMEOUT, default="15s"
            ): validate_protocol_timeout,
            # Protocol selection: auto (default), apc, cyberpower, generic, megatec
            cv.Optional(CONF_PROTOCOL, default="auto"): cv.one_of(
                "auto", "apc", "cyberpower", "generic", "megatec", lower=True
            ),
            # Fallback nominal voltage (European 230V default for international compatibility)
            cv.Optional(CONF_FALLBACK_NOMINAL_VOLTAGE, default="230V"): validate_fallback_nominal_voltage,
        }
    ).extend(cv.polling_component_schema("30s"))
     .extend(cv.COMPONENT_SCHEMA),
    validate_usb_config,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_simulation_mode(config[CONF_SIMULATION_MODE]))
    
    # USB IDs are now optional - only set if provided for troubleshooting
    if CONF_USB_VENDOR_ID in config:
        cg.add(var.set_usb_vendor_id(config[CONF_USB_VENDOR_ID]))
    if CONF_USB_PRODUCT_ID in config:
        cg.add(var.set_usb_product_id(config[CONF_USB_PRODUCT_ID]))
    
    cg.add(var.set_protocol_timeout(config[CONF_PROTOCOL_TIMEOUT]))
    cg.add(var.set_protocol_selection(config[CONF_PROTOCOL]))
    cg.add(var.set_fallback_nominal_voltage(config[CONF_FALLBACK_NOMINAL_VOLTAGE]))
