"""ESPHome Number Platform for UPS HID Component"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import number
from esphome.const import (
    CONF_ID,
    DEVICE_CLASS_DURATION,
    UNIT_SECOND,
    ENTITY_CATEGORY_CONFIG,
)
from . import ups_hid_ns, UpsHidComponent, CONF_UPS_HID_ID

DEPENDENCIES = ["ups_hid"]

UpsDelayNumber = ups_hid_ns.class_("UpsDelayNumber", number.Number, cg.Component)

CONF_DELAY_TYPE = "delay_type"

DelayType = ups_hid_ns.enum("DelayType")
DELAY_TYPES = {
    "shutdown": DelayType.DELAY_SHUTDOWN,
    "start": DelayType.DELAY_START,
    "reboot": DelayType.DELAY_REBOOT,
}

CONFIG_SCHEMA = number.number_schema(
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

async def to_code(config):
    var = await number.new_number(
        config,
        min_value=config["min_value"],
        max_value=config["max_value"],
        step=config["step"],
    )
    
    ups_hid = await cg.get_variable(config[CONF_UPS_HID_ID])
    cg.add(var.set_parent(ups_hid))
    cg.add(var.set_delay_type(config[CONF_DELAY_TYPE]))
    cg.add(ups_hid.register_delay_number(var))