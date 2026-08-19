"""NUT Server Component for ESPHome - Configuration and code generation."""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import (
    CONF_ID,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)

DEPENDENCIES = ["esp32", "network", "ups_hid"]
AUTO_LOAD = []
MULTI_CONF = False

CONF_UPS_HID_ID = "ups_hid_id"
CONF_MAX_CLIENTS = "max_clients"
CONF_UPS_NAME = "ups_name"

nut_server_ns = cg.esphome_ns.namespace("nut_server")
NutServerComponent = nut_server_ns.class_("NutServerComponent", cg.Component)

# Import ups_hid namespace
ups_hid_ns = cg.esphome_ns.namespace("ups_hid")
UpsHidComponent = ups_hid_ns.class_("UpsHidComponent", cg.PollingComponent)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(NutServerComponent),
        cv.Required(CONF_UPS_HID_ID): cv.use_id(UpsHidComponent),
        cv.Optional(CONF_PORT, default=3493): cv.port,
        cv.Optional(CONF_USERNAME, default="nutuser"): cv.string,
        cv.Optional(CONF_PASSWORD, default=""): cv.string,
        cv.Optional(CONF_MAX_CLIENTS, default=4): cv.int_range(min=1, max=10),
        cv.Optional(CONF_UPS_NAME): cv.string,
    }
).extend(cv.COMPONENT_SCHEMA)


def validate_config(config):
    """Validate NUT server configuration."""
    # Validate authentication
    if config[CONF_PASSWORD] and not config[CONF_USERNAME]:
        raise cv.Invalid("Username is required when password is set")
    
    return config


CONFIG_SCHEMA = CONFIG_SCHEMA.add_extra(validate_config)


async def to_code(config):
    """Generate C++ code for NUT server component."""
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    
    # Get reference to UPS HID component
    ups_hid = await cg.get_variable(config[CONF_UPS_HID_ID])
    cg.add(var.set_ups_hid(ups_hid))
    
    # Set port
    cg.add(var.set_port(config[CONF_PORT]))
    
    # Set authentication
    cg.add(var.set_username(config[CONF_USERNAME]))
    if CONF_PASSWORD in config:
        cg.add(var.set_password(config[CONF_PASSWORD]))
    
    # Set max clients
    cg.add(var.set_max_clients(config[CONF_MAX_CLIENTS]))
    
    # Set UPS name - use custom name if provided, otherwise use component ID
    if CONF_UPS_NAME in config:
        ups_name = config[CONF_UPS_NAME]
    else:
        ups_name = str(config[CONF_UPS_HID_ID])
    cg.add(var.set_ups_name(ups_name))