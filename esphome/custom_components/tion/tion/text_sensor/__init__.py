import esphome.codegen as cg
from esphome.components import text_sensor
from esphome.const import CONF_ENTITY_CATEGORY, CONF_ICON, ENTITY_CATEGORY_DIAGNOSTIC

from .. import new_pc, cgp, tion_ns

TionTextSensor = tion_ns.class_("TionTextSensor", text_sensor.TextSensor, cg.Component)

PC = new_pc(
    {
        "errors": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_ICON: cgp.ICON_FAN_ALERT,
        },
        "firmware_version": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_ICON: cgp.ICON_GIT,
        },
        "hardware_version": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_ICON: cgp.ICON_CHIP,
        },
        # aliases
        "hardware": "hardware_version",
        "firmware": "firmware_version",
    }
)


CONFIG_SCHEMA = PC.text_sensor_schema(TionTextSensor)


async def to_code(config: dict):
    await PC.new_text_sensor(config)
