import esphome.codegen as cg
from esphome.components import select
from esphome.const import CONF_ENTITY_CATEGORY, CONF_ICON, ENTITY_CATEGORY_CONFIG

from .. import cgp, new_pc, tion_ns

TionSelect = tion_ns.class_("TionSelect", select.Select, cg.Component)

PC = new_pc(
    {
        "air_intake": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_CONFIG,
            CONF_ICON: cgp.ICON_VALVE,
        },
        "presets": {
            CONF_ICON: cgp.ICON_TUNE,
        },
        # aliases
        "gate_position": "air_intake",
    }
)

CONFIG_SCHEMA = PC.select_schema(TionSelect)


async def to_code(config: dict):
    await PC.new_select(config)
