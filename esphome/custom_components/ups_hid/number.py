"""ESPHome Number Platform for UPS HID Component"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import number
from esphome.const import (
    CONF_ID,
    DEVICE_CLASS_DURATION,
    DEVICE_CLASS_VOLTAGE,
    UNIT_SECOND,
    UNIT_VOLT,
    ENTITY_CATEGORY_CONFIG,
)
from . import ups_hid_ns, UpsHidComponent, CONF_UPS_HID_ID

DEPENDENCIES = ["ups_hid"]

UpsDelayNumber = ups_hid_ns.class_("UpsDelayNumber", number.Number, cg.Component)
UpsCalibrationNumber = ups_hid_ns.class_("UpsCalibrationNumber", number.Number, cg.Component)

CONF_DELAY_TYPE = "delay_type"
CONF_CALIBRATION_TYPE = "calibration_type"

DelayType = ups_hid_ns.enum("DelayType")
DELAY_TYPES = {
    "shutdown": DelayType.DELAY_SHUTDOWN,
    "start": DelayType.DELAY_START,
    "reboot": DelayType.DELAY_REBOOT,
}

CalibrationType = ups_hid_ns.enum("CalibrationType")
CALIBRATION_TYPES = {
    "battery_voltage_high": CalibrationType.BATTERY_VOLTAGE_HIGH,
    "battery_voltage_low": CalibrationType.BATTERY_VOLTAGE_LOW,
}

DELAY_SCHEMA = number.number_schema(
    UpsDelayNumber,
    unit_of_measurement=UNIT_SECOND,
    device_class=DEVICE_CLASS_DURATION,
    entity_category=ENTITY_CATEGORY_CONFIG,
).extend(
    {
        cv.GenerateID(CONF_UPS_HID_ID): cv.use_id(UpsHidComponent),
        cv.Required(CONF_DELAY_TYPE): cv.enum(DELAY_TYPES, lower=True),
        cv.Optional("min_value", default=0): cv.float_range(min=0, max=3600),
        cv.Optional("max_value", default=600): cv.float_range(min=0, max=7200),
        cv.Optional("step", default=10): cv.positive_float,
    }
)

# Live-tunable battery percentage calibration (0%/100% voltage points).
# Purely local to the ESP32 - unlike the delay numbers above, this never
# talks to the UPS over USB, it just feeds back into the component's own
# battery-percentage estimate (see protocol_megatec.cpp). Useful for
# protocols/devices (like Megatec/Q1) that only report a raw battery
# voltage, not a charge percentage.
CALIBRATION_SCHEMA = number.number_schema(
    UpsCalibrationNumber,
    unit_of_measurement=UNIT_VOLT,
    device_class=DEVICE_CLASS_VOLTAGE,
    entity_category=ENTITY_CATEGORY_CONFIG,
).extend(
    {
        cv.GenerateID(CONF_UPS_HID_ID): cv.use_id(UpsHidComponent),
        cv.Required(CONF_CALIBRATION_TYPE): cv.enum(CALIBRATION_TYPES, lower=True),
        cv.Optional("min_value", default=0): cv.float_range(min=0, max=60),
        cv.Optional("max_value", default=30): cv.float_range(min=0, max=60),
        cv.Optional("step", default=0.1): cv.positive_float,
    }
)

# A given number: entry is either a delay number (identified by delay_type)
# or a calibration number (identified by calibration_type) - cv.Any tries
# each in turn and uses whichever one actually validates.
CONFIG_SCHEMA = cv.Any(DELAY_SCHEMA, CALIBRATION_SCHEMA)


async def to_code(config):
    var = await number.new_number(
        config,
        min_value=config["min_value"],
        max_value=config["max_value"],
        step=config["step"],
    )
    # number.new_number() only registers the entity, not the Component -
    # without this, Component::setup() (and thus UpsCalibrationNumber's/
    # UpsDelayNumber's setup() override, where the initial displayed value
    # gets published) is never called by App.setup().
    await cg.register_component(var, config)

    ups_hid = await cg.get_variable(config[CONF_UPS_HID_ID])
    cg.add(var.set_parent(ups_hid))

    if CONF_DELAY_TYPE in config:
        cg.add(var.set_delay_type(config[CONF_DELAY_TYPE]))
        cg.add(ups_hid.register_delay_number(var))
    else:
        cg.add(var.set_calibration_type(config[CONF_CALIBRATION_TYPE]))
