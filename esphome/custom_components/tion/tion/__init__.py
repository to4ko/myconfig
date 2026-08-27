import logging
from typing import Any

import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.cpp_generator as cpp
import esphome.final_validate as fv
from esphome import automation, core
from esphome.components import sensor as esphome_sensor
from esphome.const import (
    CONF_CO2,
    CONF_FORCE_UPDATE,
    CONF_HEATER,
    CONF_ID,
    CONF_LAMBDA,
    CONF_ON_STATE,
    CONF_POWER,
    CONF_TEMPERATURE,
    CONF_TYPE,
)
from esphome.core import ID
from esphome.cpp_generator import MockObjClass

from .. import cgp, vport  # pylint: disable=relative-beyond-top-level

CODEOWNERS = ["@dentra"]
AUTO_LOAD = ["etl", "tion-api", "cgp"]

CONF_TION_ID = "tion_id"
CONF_COMPONENT_CLASS = cgp.CONF_COMPONENT_CLASS

CONF_PRESETS = "presets"
CONF_FAN_SPEED = "fan_speed"
CONF_GATE_POSITION = "gate_position"
CONF_AUTO = "auto"
CONF_BUTTON_PRESETS = "button_presets"

CONF_STATE_TIMEOUT = "state_timeout"
CONF_STATE_WARNOUT = "state_warnout"
CONF_BATCH_TIMEOUT = "batch_timeout"

CONF_SETPOINT = "setpoint"
CONF_MIN_FAN_SPEED = f"min_{CONF_FAN_SPEED}"
CONF_MAX_FAN_SPEED = f"max_{CONF_FAN_SPEED}"
CONF_PI_CONTROLLER = "pi_controller"
CONF_KP = "kp"
CONF_TI = "ti"
CONF_DB = "db"

tion_ns = cg.esphome_ns.namespace("tion")
dentra_tion_ns = cg.global_ns.namespace("dentra").namespace("tion")

TionVPortApi = tion_ns.class_("TionVPortApi")
TionApiComponent = tion_ns.class_("TionApiComponent", cg.Component)

TionStateRef = dentra_tion_ns.namespace("TionState").operator("ref").operator("const")
TionGatePosition = dentra_tion_ns.namespace("TionGatePosition")

StateTrigger = tion_ns.class_("StateTrigger", automation.Trigger.template(TionStateRef))

BREEZER_TYPES = {
    "o2": tion_ns.class_("TionO2ApiComponent", TionApiComponent),
    "3s": tion_ns.class_("Tion3sApiComponent", TionApiComponent),
    "4s": tion_ns.class_("Tion4sApiComponent", TionApiComponent),
    "lt": tion_ns.class_("TionLtApiComponent", TionApiComponent),
}

PRESET_GATE_POSITIONS = {
    "none": TionGatePosition.NONE,
    "outdoor": TionGatePosition.OUTDOOR,
    "indoor": TionGatePosition.INDOOR,
    "mixed": TionGatePosition.MIXED,
}


PRESET_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_POWER, default=True): cv.boolean,
        cv.Optional(CONF_HEATER): cv.boolean,
        cv.Optional(CONF_FAN_SPEED, default=0): cv.int_range(min=0, max=6),
        cv.Optional(CONF_TEMPERATURE, default=0): cv.int_range(min=-30, max=30),
        cv.Optional(CONF_GATE_POSITION, default="none"): cv.one_of(
            *PRESET_GATE_POSITIONS, lower=True
        ),
        cv.Optional(CONF_AUTO): cv.boolean,
    }
)

BUTTON_PRESETS_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_TEMPERATURE): cv.All(
            cv.ensure_list(cv.int_range(min=1, max=25)), cv.Length(min=3, max=3)
        ),
        cv.Required(CONF_FAN_SPEED): cv.All(
            cv.ensure_list(cv.int_range(min=1, max=6)), cv.Length(min=3, max=3)
        ),
    }
)

AUTO_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_CO2): cv.use_id(esphome_sensor.Sensor),
        cv.Optional(CONF_SETPOINT): cv.int_range(500, 1400),
        cv.Inclusive(CONF_MIN_FAN_SPEED, "auto_fan_speed"): cv.int_range(0, 5),
        cv.Inclusive(CONF_MAX_FAN_SPEED, "auto_fan_speed"): cv.int_range(1, 6),
        cv.Exclusive(CONF_PI_CONTROLLER, "auto_mode"): cv.Any(
            {
                cv.Optional(CONF_KP, default=0.2736): cv.float_range(min=0.001),
                cv.Optional(CONF_TI, default=8): cv.float_range(min=0.001),
                cv.Optional(CONF_DB, default=20): cv.int_range(-100, 100),
            },
            None,
        ),
        cv.Exclusive(CONF_LAMBDA, "auto_mode"): cv.returning_lambda,
    }
)


def check_type(key, typ, required: bool = False):
    return cgp.validate_type(key, typ, required)


CONFIG_SCHEMA = cv.All(
    cv.ensure_list(
        cv.Schema(
            {
                cv.GenerateID(): cv.declare_id(TionApiComponent),
                cv.GenerateID(CONF_TION_ID): cv.declare_id(TionVPortApi),
                cv.Required(CONF_TYPE): cv.one_of(*BREEZER_TYPES, lower=True),
                cv.Optional(CONF_BUTTON_PRESETS): BUTTON_PRESETS_SCHEMA,
                cv.Optional(CONF_STATE_TIMEOUT, default="3s"): cv.update_interval,
                cv.Optional(
                    CONF_BATCH_TIMEOUT, default="200ms"
                ): cv.positive_time_period_milliseconds,
                cv.Optional(CONF_FORCE_UPDATE): cv.boolean,
                cv.Optional(CONF_PRESETS): cv.Schema({cv.string_strict: PRESET_SCHEMA}),
                cv.Optional(CONF_ON_STATE): cgp.automation_schema(StateTrigger),
                cv.Optional(CONF_AUTO): AUTO_SCHEMA,
            }
        )
        .extend(vport.VPORT_CLIENT_SCHEMA)
        .extend(cv.polling_component_schema("60s")),
        cgp.validate_type(CONF_BUTTON_PRESETS, "lt"),
    ),
)


async def new_vport_api_wrapper(config: dict, component_class: MockObjClass):
    # get vport instance
    prt = await vport.vport_get_var(config)
    # create TionVPortApi wrapper
    api = cg.new_Pvariable(
        config[CONF_TION_ID],
        cg.TemplateArguments(
            vport.vport_find(config).type.class_("frame_spec_type"),
            component_class.class_("Api"),
        ),
        prt,
    )
    return prt, api


async def _setup_tion_api(config: dict):
    component_class: MockObjClass = BREEZER_TYPES[config[CONF_TYPE]]

    prt, api = await new_vport_api_wrapper(config, component_class)
    cg.add(prt.set_api(api))

    component_id: ID = config[CONF_ID]
    component_id.type = component_class
    var = cg.new_Pvariable(config[CONF_ID], api, prt.get_type())
    await cg.register_component(var, config)

    # var.set_component_source(str) больше не существует в ESPHome 2026.x
    # (см. тот же фикс и подробное объяснение в cgp/pc.py new_component()) -
    # cg.register_component() выше уже регистрирует источник компонента сам.
    # cg.add_library("tion-api", None, "https://github.com/dentra/tion-api")
    cg.add_build_flag("-DTION_ESPHOME")

    cg.add(var.set_state_timeout(config[CONF_STATE_TIMEOUT]))
    cg.add(var.set_batch_timeout(config[CONF_BATCH_TIMEOUT]))
    cgp.setup_value(config, CONF_FORCE_UPDATE, var.set_force_update)

    return var


def _setup_tion_api_presets(config: dict, var: cg.MockObj):
    if CONF_PRESETS not in config:
        return

    presets = set()
    for preset in config[CONF_PRESETS]:
        preset_name = str(preset).strip()
        if preset_name.lower() == "none":
            logging.warning("Preset 'none' is reserved")
            continue
        if preset_name.lower() in presets:
            logging.warning("Preset '%s' is already exists", preset)
            continue
        preset = config[CONF_PRESETS][preset_name]
        cg.add(
            var.add_preset(
                preset_name,
                cg.StructInitializer(
                    "",
                    ("target_temperature", preset[CONF_TEMPERATURE]),
                    ("heater_state", int(preset.get(CONF_HEATER, -1))),
                    ("power_state", int(preset.get(CONF_POWER, -1))),
                    ("fan_speed", preset[CONF_FAN_SPEED]),
                    (
                        "gate_position",
                        PRESET_GATE_POSITIONS[preset[CONF_GATE_POSITION]],
                    ),
                    ("auto_state", int(preset.get(CONF_AUTO, -1))),
                ),
            )
        )

        presets.add(preset_name)


def _setup_tion_api_button_presets(config: dict, var: cg.MockObj):
    if CONF_BUTTON_PRESETS not in config:
        return
    button_presets = config[CONF_BUTTON_PRESETS]

    cg.add(
        var.set_button_presets(
            cg.StructInitializer(
                "",
                ("tmp", button_presets[CONF_TEMPERATURE]),
                ("fan", button_presets[CONF_FAN_SPEED]),
            )
        )
    )


async def _setup_auto(config: dict, var):
    api = var.Papi()

    code = f"""
auto *call = {var}->make_call();
if ({api}->auto_update(x, call)) {{
  call->perform();
}}
"""

    lam = await cg.process_lambda(
        value=core.Lambda(code.strip()), parameters=[(cg.float_, "x")], capture=""
    )

    cg.add(cg.MockObj(config[CONF_CO2].id, "->").add_on_state_callback(lam))

    cgp.setup_value(config, CONF_SETPOINT, api.set_auto_setpoint)
    cgp.setup_value(config, CONF_MIN_FAN_SPEED, api.set_auto_min_fan_speed)
    cgp.setup_value(config, CONF_MAX_FAN_SPEED, api.set_auto_max_fan_speed)

    if CONF_PI_CONTROLLER in config:
        cgp.setup_values(
            config[CONF_PI_CONTROLLER] or {},
            [CONF_KP, CONF_TI, CONF_DB],
            api.set_auto_pi_data,
        )

    await cgp.setup_lambda(
        config,
        CONF_LAMBDA,
        api.set_auto_update_func,
        parameters=[(cg.uint16, "x")],
        return_type=cg.uint8,
    )


async def to_code(config: dict):
    for conf in config:
        var = await _setup_tion_api(conf)
        _setup_tion_api_presets(conf, var)
        _setup_tion_api_button_presets(conf, var)
        await cgp.setup_automation(conf, CONF_ON_STATE, var, (TionStateRef, "x"))
        if CONF_AUTO in conf:
            await _setup_auto(conf[CONF_AUTO], var)


def new_pc(pc_cfg: dict[str, str | dict[str, Any]]):
    def get_component_type() -> str:
        import inspect

        stack = inspect.stack()
        frame = stack[2][0]
        ctyp = inspect.getmodule(frame).__name__.split(".")[-1:][0]

        return ctyp

    class TionPC(cgp.PC):
        def get_type_component(self, config: dict):
            cls = super().get_type_component(config)
            if cls and not isinstance(cls, cg.MockObjClass):
                import copy

                # creates same object class as base entity
                cpy: cg.MockObjClass = copy.deepcopy(config[CONF_ID].type)
                cls = str(cls)
                # additionally copy ns
                if "::" not in cls:
                    cls = "::".join(str(cpy.base).split("::")[:-1] + [cls])
                cpy.base = cls
                cls = cpy
            return cls

        def get_type_class(self, config: dict):
            ct_cls = self.get_type_component(config)
            # skip pc components with declared classes
            if ct_cls:
                return None
            pc_typ = self.get_type(config)
            # skip non pc components e.g. fan and climate
            if not pc_typ:
                return None
            ct_typ = self.component_type
            # special case for the swithc namespace
            if ct_typ == "switch":
                ct_typ = f"{ct_typ}_"
            pc_typ = pc_typ.replace("_", " ").title().replace(" ", "")
            return tion_ns.class_(f"property_controller::{ct_typ}::{pc_typ}")

    return TionPC(TionApiComponent, CONF_TION_ID, pc_cfg, get_component_type())
