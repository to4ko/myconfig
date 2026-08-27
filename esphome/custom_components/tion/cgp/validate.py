import esphome.config_validation as cv
from esphome.const import CONF_TYPE


def validate_type(key, typ, required: bool = False):
    def validator(config):
        if key in config and config[CONF_TYPE] != typ:
            raise cv.Invalid(f"{key} is not valid for the type {typ}")
        if required and config[CONF_TYPE] == typ and key not in config:
            raise cv.Invalid(f"{key} is requred for the type {typ}")
        return config

    return validator
