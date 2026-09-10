import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .core.const import *


class FlowHandler(ConfigFlow, domain=DOMAIN):
    async def async_step_import(self, user_input: dict = None):
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input:
            return self.async_create_entry(
                title="Hass Diagnostics", data={}, options=user_input
            )

        return self.async_show_form(step_id="user", data_schema=data_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return OptionsFlowHandler()


# noinspection PyUnusedLocal
class OptionsFlowHandler(OptionsFlow):
    @property
    def config_entry(self):
        return self.hass.config_entries.async_get_entry(self.handler)

    async def async_step_init(self, user_input: dict = None):
        if user_input:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            return self.async_create_entry(title="", data=user_input)

        data = data_schema(self.config_entry.options)
        return self.async_show_form(step_id="init", data_schema=data)


def data_schema(defaults=None) -> vol.Schema:
    schema = {
        vol.Required(SMART_LOG, default=True): bool,
        vol.Required(START_TIME, default=True): bool,
        vol.Required(UNSAFE_STATE, default=True): bool,
    }
    if defaults:
        for key in schema:
            if (value := defaults.get(key.schema)) is not None:
                key.default = vol.default_factory(value)
    return vol.Schema(schema)
