import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import button
from esphome.const import CONF_ID
from . import ups_hid_ns, CONF_UPS_HID_ID, UpsHidComponent

DEPENDENCIES = ["ups_hid"]

UpsHidButton = ups_hid_ns.class_("UpsHidButton", button.Button, cg.Component)

CONF_BEEPER_ACTION = "beeper_action"
CONF_TEST_ACTION = "test_action"

BEEPER_ACTIONS = {
    "enable": "enable",
    "disable": "disable", 
    "mute": "mute",
    "test": "test"
}

TEST_ACTIONS = {
    "battery_quick": "battery_quick",
    "battery_deep": "battery_deep",
    "battery_stop": "battery_stop",
    "ups_test": "ups_test",
    "ups_stop": "ups_stop"
}

# Support either beeper_action or test_action, but not both
def validate_button_config(config):
    beeper_action = config.get(CONF_BEEPER_ACTION)
    test_action = config.get(CONF_TEST_ACTION)
    
    if beeper_action is not None and test_action is not None:
        raise cv.Invalid("Cannot specify both 'beeper_action' and 'test_action' on the same button")
    
    if beeper_action is None and test_action is None:
        raise cv.Invalid("Must specify either 'beeper_action' or 'test_action'")
    
    return config

CONFIG_SCHEMA = cv.All(
    button.button_schema(UpsHidButton).extend({
        cv.GenerateID(CONF_UPS_HID_ID): cv.use_id(UpsHidComponent),
        cv.Optional(CONF_BEEPER_ACTION): cv.enum(BEEPER_ACTIONS, lower=True),
        cv.Optional(CONF_TEST_ACTION): cv.enum(TEST_ACTIONS, lower=True),
    }).extend(cv.COMPONENT_SCHEMA),
    validate_button_config,
)


async def to_code(config):
    var = await button.new_button(config)
    await cg.register_component(var, config)

    parent = await cg.get_variable(config[CONF_UPS_HID_ID])
    cg.add(var.set_ups_hid_parent(parent))
    
    # Set action based on which type was configured
    if CONF_BEEPER_ACTION in config:
        cg.add(var.set_beeper_action(config[CONF_BEEPER_ACTION]))
    elif CONF_TEST_ACTION in config:
        cg.add(var.set_test_action(config[CONF_TEST_ACTION]))