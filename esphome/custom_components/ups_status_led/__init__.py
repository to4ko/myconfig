import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import light, time, switch, number, text_sensor
from esphome.const import (
    CONF_ID,
    CONF_BRIGHTNESS,
    CONF_TIME_ID,
)

CONF_ENABLED = "enabled"

DEPENDENCIES = ["ups_hid", "light"]
AUTO_LOAD = ["switch", "number", "text_sensor"]

ups_status_led_ns = cg.esphome_ns.namespace("ups_status_led")
UpsStatusLedComponent = ups_status_led_ns.class_("UpsStatusLedComponent", cg.Component)

BatteryColorMode = ups_status_led_ns.enum("BatteryColorMode", is_class=True)
BATTERY_COLOR_MODES = {
    "discrete": BatteryColorMode.DISCRETE,
    "gradient": BatteryColorMode.GRADIENT,
}

CONF_UPS_HID_ID = "ups_hid_id"
CONF_LIGHT_ID = "light_id"
CONF_NIGHT_MODE = "night_mode"
CONF_START_TIME = "start_time"
CONF_END_TIME = "end_time"
CONF_BATTERY_COLOR_MODE = "battery_color_mode"
CONF_BATTERY_LOW_THRESHOLD = "battery_low_threshold"
CONF_BATTERY_WARNING_THRESHOLD = "battery_warning_threshold"

def validate_time(value):
    """Validate time format HH:MM"""
    if isinstance(value, str):
        parts = value.split(":")
        if len(parts) != 2:
            raise cv.Invalid("Time must be in format HH:MM")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
            if not (0 <= hour <= 23):
                raise cv.Invalid("Hour must be between 0 and 23")
            if not (0 <= minute <= 59):
                raise cv.Invalid("Minute must be between 0 and 59")
            return {"hour": hour, "minute": minute}
        except ValueError:
            raise cv.Invalid("Invalid time format")
    return value

NIGHT_MODE_SCHEMA = cv.Schema({
    cv.Optional(CONF_ENABLED, default=True): cv.boolean,
    cv.Optional(CONF_BRIGHTNESS, default="30%"): cv.percentage,  # Changed from 15% to 30%
    cv.Optional(CONF_START_TIME, default="22:00"): validate_time,
    cv.Optional(CONF_END_TIME, default="07:00"): validate_time,
})

CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(UpsStatusLedComponent),
    cv.Required(CONF_UPS_HID_ID): cv.use_id("ups_hid.UpsHidComponent"),
    cv.Required(CONF_LIGHT_ID): cv.use_id(light.LightState),
    cv.Optional(CONF_TIME_ID): cv.use_id(time.RealTimeClock),
    
    cv.Optional(CONF_ENABLED, default=True): cv.boolean,
    cv.Optional(CONF_BRIGHTNESS, default="80%"): cv.percentage,
    cv.Optional(CONF_BATTERY_COLOR_MODE, default="discrete"): cv.enum(
        BATTERY_COLOR_MODES, lower=True
    ),
    
    cv.Optional(CONF_NIGHT_MODE): NIGHT_MODE_SCHEMA,
    
    cv.Optional(CONF_BATTERY_LOW_THRESHOLD, default=20.0): cv.float_range(
        min=0, max=100
    ),
    cv.Optional(CONF_BATTERY_WARNING_THRESHOLD, default=50.0): cv.float_range(
        min=0, max=100
    ),
}).extend(cv.COMPONENT_SCHEMA)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    
    # Link UPS HID component
    ups = await cg.get_variable(config[CONF_UPS_HID_ID])
    cg.add(var.set_ups_hid(ups))
    
    # Link Light component
    light_var = await cg.get_variable(config[CONF_LIGHT_ID])
    cg.add(var.set_light(light_var))
    
    # Optional time component for night mode
    if CONF_TIME_ID in config:
        time_var = await cg.get_variable(config[CONF_TIME_ID])
        cg.add(var.set_time(time_var))
    
    # Basic configuration
    cg.add(var.set_enabled(config[CONF_ENABLED]))
    cg.add(var.set_brightness(config[CONF_BRIGHTNESS]))
    cg.add(var.set_battery_color_mode(config[CONF_BATTERY_COLOR_MODE]))
    
    # Battery thresholds
    cg.add(var.set_battery_low_threshold(config[CONF_BATTERY_LOW_THRESHOLD]))
    cg.add(var.set_battery_warning_threshold(config[CONF_BATTERY_WARNING_THRESHOLD]))
    
    # Night mode configuration
    if CONF_NIGHT_MODE in config:
        night_config = config[CONF_NIGHT_MODE]
        cg.add(var.set_night_mode_enabled(night_config[CONF_ENABLED]))
        cg.add(var.set_night_mode_brightness(night_config[CONF_BRIGHTNESS]))
        
        start_time = night_config[CONF_START_TIME]
        cg.add(var.set_night_mode_start_time(start_time["hour"], start_time["minute"]))
        
        end_time = night_config[CONF_END_TIME]
        cg.add(var.set_night_mode_end_time(end_time["hour"], end_time["minute"]))
    
    # Note: For Home Assistant control entities, users should manually add
    # switch, number, and text_sensor entities in their configuration.
    # This provides better flexibility and follows ESPHome best practices.