import esphome.codegen as cg
from esphome.components import fan

from .. import new_pc, tion_ns

TionFan = tion_ns.class_("TionFan", fan.Fan, cg.Component)

PC = new_pc(None)

CONFIG_SCHEMA = PC.fan_schema(TionFan)


async def to_code(config: dict):
    await PC.new_fan(config)
