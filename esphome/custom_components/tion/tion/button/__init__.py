import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import button, switch
from esphome.const import CONF_ENTITY_CATEGORY, CONF_ICON, ENTITY_CATEGORY_CONFIG

from .. import CONF_COMPONENT_CLASS, new_pc, cgp, tion_ns

AUTO_LOAD = ["switch"]

TionResetFilterConfirmSwitchT = tion_ns.class_(
    "TionResetFilterConfirmSwitch", switch.Switch
)

CONF_RESET_FILTER_CONFIRM = "confirm"

TionButton = tion_ns.class_("TionButton", button.Button, cg.Component)

PC = new_pc(
    {
        "reset_filter": {
            CONF_COMPONENT_CLASS: "TionResetFilterButton",
            CONF_ICON: cgp.ICON_WRENCH_COG,
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_CONFIG,
        },
        # "reset_errors": {
        #     CONF_ICON: "mdi:button-pointer",
        #     CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
        # },
    }
)


CONFIG_SCHEMA = PC.button_schema(
    TionButton,
    {
        cv.Optional(CONF_RESET_FILTER_CONFIRM): switch.switch_schema(
            TionResetFilterConfirmSwitchT.template(cg.Component),
            icon=cgp.ICON_WRENCH_CHECK,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    },
    [
        cgp.validate_type(CONF_RESET_FILTER_CONFIRM, "reset_filter"),
    ],
)


async def to_code(config: dict):
    var = await PC.new_button(config)
    await cgp.setup_switch(config, CONF_RESET_FILTER_CONFIRM, var.set_confirm, var)
