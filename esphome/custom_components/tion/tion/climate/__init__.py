import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import climate
from esphome.const import CONF_ICON

from .. import new_pc, cgp, tion_ns

TionClimate = tion_ns.class_("TionClimate", climate.Climate, cg.Component)


CONF_ENABLE_HEAT_COOL = "enable_heat_cool"
CONF_ENABLE_FAN_AUTO = "enable_fan_auto"

PC = new_pc(None)

CONFIG_SCHEMA = PC.climate_schema(
    TionClimate,
    {
        cv.Optional(CONF_ICON, default=cgp.ICON_AIR_FILTER): cv.icon,
        cv.Optional(CONF_ENABLE_HEAT_COOL): cv.boolean,
        cv.Optional(CONF_ENABLE_FAN_AUTO): cv.boolean,
    },
)


async def to_code(config: dict):
    var = await PC.new_climate(config)
    cgp.setup_value(config, CONF_ENABLE_HEAT_COOL, var.set_enable_heat_cool)
    cgp.setup_value(config, CONF_ENABLE_FAN_AUTO, var.set_enable_fan_auto)
