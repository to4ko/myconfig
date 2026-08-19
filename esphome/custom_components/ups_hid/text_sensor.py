import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import (
    CONF_TYPE,
)

from . import ups_hid_ns, UpsHidComponent, CONF_UPS_HID_ID

DEPENDENCIES = ["ups_hid"]

UpsHidTextSensor = ups_hid_ns.class_(
    "UpsHidTextSensor", text_sensor.TextSensor, cg.Component
)

TEXT_SENSOR_TYPES = [
    "model",
    "manufacturer",
    "status",
    "nut_status",
    "protocol",
    "serial_number",
    "firmware_version",
    "ups_beeper_status",
    "input_sensitivity",
    # Additional missing text sensor types from NUT analysis
    "battery_status",
    "battery_type",
    "battery_mfr_date",
    "ups_mfr_date",
    "ups_firmware_aux",
    "ups_test_result",
]


CONFIG_SCHEMA = text_sensor.text_sensor_schema(UpsHidTextSensor).extend(
    {
        cv.GenerateID(CONF_UPS_HID_ID): cv.use_id(UpsHidComponent),
        cv.Required(CONF_TYPE): cv.one_of(*TEXT_SENSOR_TYPES, lower=True),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_UPS_HID_ID])
    var = await text_sensor.new_text_sensor(config)
    await cg.register_component(var, config)

    sensor_type = config[CONF_TYPE]
    cg.add(var.set_sensor_type(sensor_type))
    cg.add(parent.register_text_sensor(var, sensor_type))
