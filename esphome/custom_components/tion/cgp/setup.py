import esphome.codegen as cg
import esphome.cpp_generator as cpp
from esphome import automation
from esphome.components import (
    binary_sensor,
    button,
    number,
    select,
    sensor,
    switch,
    text_sensor,
)
from esphome.const import CONF_ID, CONF_TRIGGER_ID


async def setup_variable(config: dict, key: str, setter):
    """Setup variable"""
    if key in config:
        var = await cg.get_variable(config[key])
        cg.add(setter(var))


def setup_value(config: dict, key: str, setter, skip_default_value=None):
    """Setup simple value."""
    if key in config:
        val = config[key]
        if skip_default_value is None or val != skip_default_value:
            cg.add(setter(val))


def setup_values(config: dict, keys: list[str], setter):
    """Setup all values"""
    if set(keys).issubset(config):
        cg.add(setter(*[config[key] for key in keys]))


async def setup_lambda(
    config: dict,
    key: str,
    setter,
    parameters: list[tuple[cpp.SafeExpType, str]],
    return_type: cpp.SafeExpType,
    capture="",
):
    """Setup lambda"""
    if lambda_func := config.get(key, None):
        lambda_template = await cg.process_lambda(
            lambda_func,
            parameters,
            return_type=return_type,
            capture=capture,
        )
        cg.add(setter(lambda_template))


async def setup_automation(
    config: dict, key: str, var: cg.MockObj, *args: tuple[cpp.SafeExpType, str]
):
    for conf in config.get(key, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, args, conf)


async def setup_binary_sensor(config: dict, key: str, setter):
    """Setup binary sensor"""
    if key not in config:
        return None
    sens = await binary_sensor.new_binary_sensor(config[key])
    cg.add(setter(sens))
    return sens


async def setup_sensor(config: dict, key: str, setter):
    """Setup sensor"""
    if key not in config:
        return None
    sens = await sensor.new_sensor(config[key])
    cg.add(setter(sens))
    return sens


async def setup_text_sensor(config: dict, key: str, setter):
    """Setup text sensor"""
    if key not in config:
        return None
    sens = await text_sensor.new_text_sensor(config[key])
    cg.add(setter(sens))
    return sens


async def setup_switch(config: dict, key: str, setter, parent):
    """Setup switch"""
    if key not in config:
        return None
    swch = await switch.new_switch(config[key], parent)
    cg.add(setter(swch))
    return swch


async def setup_select(config: dict, key: str, setter, parent, options):
    """Setup select"""
    if key not in config:
        return None
    conf = config[key]
    slct = cg.new_Pvariable(conf[CONF_ID], parent)
    await select.register_select(slct, conf, options=options)
    cg.add(setter(slct))
    return slct


async def setup_button(config: dict, key: str, setter, parent):
    """Setup button"""
    if key not in config:
        return None
    butn = await button.new_button(config[key], parent)
    cg.add(setter(butn))
    return butn


async def setup_number(
    config: dict, key: str, setter, min_value: int, max_value: int, step: int
):
    """Setup number"""
    if key not in config:
        return None
    numb = await number.new_number(
        config[key], min_value=min_value, max_value=max_value, step=step
    )
    cg.add(setter(numb))
    return numb
