import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.const import CONF_TRIGGER_ID


def automation_schema(trigger_class: cg.MockObjClass):
    return automation.validate_automation(
        {
            cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(trigger_class),
        }
    )
