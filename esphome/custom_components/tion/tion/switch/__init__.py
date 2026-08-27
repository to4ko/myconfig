import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import switch
from esphome.const import (
    CONF_DURATION,
    CONF_ENTITY_CATEGORY,
    CONF_HEATER,
    CONF_ICON,
    CONF_TEMPERATURE,
    ENTITY_CATEGORY_CONFIG,
)

from .. import (
    CONF_COMPONENT_CLASS,
    cgp,
    new_pc,
    tion_ns,
)

TionSwitch = tion_ns.class_("TionSwitch", switch.Switch, cg.Component)

CONF_AUTO_KP = "kp"
CONF_AUTO_TI = "ti"
CONF_AUTO_DB = "db"

PC = new_pc(
    {
        "power": {
            CONF_ICON: cgp.ICON_POWER,
        },
        "heater": {
            CONF_ICON: cgp.ICON_RADIATOR,
        },
        "sound": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_CONFIG,
            CONF_ICON: cgp.ICON_VOLUME_HIGH,
        },
        "led": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_CONFIG,
            CONF_ICON: cgp.ICON_LED_OUTLINE,
        },
        "recirculation": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_CONFIG,
            CONF_ICON: cgp.ICON_VALVE,
        },
        "boost": {
            CONF_COMPONENT_CLASS: "TionBoostSwitch",
            CONF_ICON: cgp.ICON_ROCKET_LAUNCH,
        },
        "auto": {
            CONF_ICON: cgp.ICON_FAN_AUTO,
        },
        # aliases
        "buzzer": "sound",
        "heat": "heater",
        "light": "led",
    }
)

CONFIG_SCHEMA = PC.switch_schema(
    TionSwitch,
    {
        # boost duration
        cv.Optional(CONF_DURATION): cv.All(
            cv.positive_time_period_minutes,
            cv.Range(min=cv.TimePeriod(minutes=1), max=cv.TimePeriod(minutes=60)),
        ),
        # boost heater
        cv.Optional(CONF_HEATER): cv.boolean,
        # boost temperature
        cv.Optional(CONF_TEMPERATURE): cv.int_range(-30, 30),
    },
    [
        cgp.validate_type(CONF_DURATION, "boost"),
        cgp.validate_type(CONF_HEATER, "boost"),
        cgp.validate_type(CONF_TEMPERATURE, "boost"),
    ],
)


async def to_code(config: dict):
    var = await PC.new_switch(config)

    # boost settings
    cgp.setup_value(config, CONF_DURATION, var.set_boost_time)
    cgp.setup_value(config, CONF_HEATER, var.set_boost_heater_state)
    cgp.setup_value(config, CONF_TEMPERATURE, var.set_boost_target_temperature)
