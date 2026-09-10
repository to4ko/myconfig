from types import MappingProxyType

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import callback

from . import DOMAIN, utils

SCHEMA = {
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_MAC): cv.string,
}


def vol_schema(schema: dict, defaults: MappingProxyType | None) -> vol.Schema:
    if defaults:
        for key in schema:
            if (value := defaults.get(key.schema)) is not None:
                key.default = vol.default_factory(value)
    return vol.Schema(schema)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            host = user_input.get(CONF_HOST)
            mac = user_input.get(CONF_MAC)
            title = utils.get_title(self.hass, host, mac) or host or mac or ""
            return self.async_create_entry(title=title, data={}, options=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema(SCHEMA))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", options=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol_schema(SCHEMA, self.config_entry.options),
        )
