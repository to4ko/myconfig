import esphome.codegen as cg
from esphome.components import binary_sensor
from esphome.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_RUNNING,
    ENTITY_CATEGORY_DIAGNOSTIC,
)

from .. import new_pc, cgp, tion_ns

TionBinarySensor = tion_ns.class_(
    "TionBinarySensor", binary_sensor.BinarySensor, cg.Component
)

PC = new_pc(
    {
        "power": {
            CONF_ICON: cgp.ICON_POWER,
        },
        "heater": {
            CONF_ICON: cgp.ICON_RADIATOR,
        },
        "sound": {
            CONF_ICON: cgp.ICON_VOLUME_HIGH,
        },
        "led": {
            CONF_ICON: cgp.ICON_LED_OUTLINE,
        },
        "filter": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        },
        "gate": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_OPENING,
        },
        "heating": {
            CONF_ICON: cgp.ICON_RADIATOR,
        },
        "error": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        },
        "gate_error": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        },
        "boost": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_RUNNING,
            CONF_ICON: cgp.ICON_ROCKET_LAUNCH,
        },
        "state": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        },
        "auto": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_RUNNING,
            CONF_ICON: cgp.ICON_FAN_AUTO,
        },
        # aliases
        "buzzer": "sound",
        "heat": "heater",
        "light": "led",
        "gate_position": "gate",
        "gate_state": "gate",
        "damper": "gate",
    }
)

CONFIG_SCHEMA = PC.binary_sensor_schema(TionBinarySensor)


async def to_code(config: dict):
    await PC.new_binary_sensor(config)
