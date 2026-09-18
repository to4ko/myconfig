import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import button
from esphome.const import CONF_ID
from . import ups_hid_ns, CONF_UPS_HID_ID, UpsHidComponent

DEPENDENCIES = ["ups_hid"]

UpsHidButton = ups_hid_ns.class_("UpsHidButton", button.Button, cg.Component)

CONF_BEEPER_ACTION = "beeper_action"
CONF_TEST_ACTION = "test_action"
CONF_USB_ACTION = "usb_action"

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

# Power-cycles the USB port (cuts and restores VBUS) - the same recovery a
# physical cable unplug/replug gives. Only meaningful on ESP32 (real USB
# host hardware); a no-op in simulation mode.
USB_ACTIONS = {
    "reset_power": "reset_power",
}

# Support exactly one of beeper_action / test_action / usb_action
def validate_button_config(config):
    beeper_action = config.get(CONF_BEEPER_ACTION)
    test_action = config.get(CONF_TEST_ACTION)
    usb_action = config.get(CONF_USB_ACTION)

    actions_set = sum(a is not None for a in (beeper_action, test_action, usb_action))

    if actions_set > 1:
        raise cv.Invalid("Specify only one of 'beeper_action', 'test_action', or 'usb_action' on the same button")

    if actions_set == 0:
        raise cv.Invalid("Must specify one of 'beeper_action', 'test_action', or 'usb_action'")

    return config

CONFIG_SCHEMA = cv.All(
    button.button_schema(UpsHidButton).extend({
        cv.GenerateID(CONF_UPS_HID_ID): cv.use_id(UpsHidComponent),
        cv.Optional(CONF_BEEPER_ACTION): cv.enum(BEEPER_ACTIONS, lower=True),
        cv.Optional(CONF_TEST_ACTION): cv.enum(TEST_ACTIONS, lower=True),
        cv.Optional(CONF_USB_ACTION): cv.enum(USB_ACTIONS, lower=True),
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
    elif CONF_USB_ACTION in config:
        cg.add(var.set_usb_action(config[CONF_USB_ACTION]))