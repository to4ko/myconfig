#  Copyright (c) 2019-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
"""
The Gismeteo component.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""

import logging
from collections.abc import Mapping
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientConnectorError, ClientError
from async_timeout import timeout
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import callback

from . import _get_api_client, forecast_days_int  # pylint: disable=unused-import
from .api import ApiError
from .const import (  # pylint: disable=unused-import
    CONF_ADD_SENSORS,
    CONF_FORECAST_DAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type ConfigType = Mapping[str, Any] | None


class GismeteoFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Gismeteo."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Init config flow."""
        self._errors = {}

    async def async_step_import(
        self, platform_config: ConfigType
    ) -> config_entries.ConfigFlowResult:
        """
        Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if self._async_current_entries():
            return self.async_abort(reason="no_mixed_config")

        return self.async_create_entry(title="configuration.yaml", data=platform_config)

    async def async_step_user(
        self, user_input: ConfigType = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        for entry in self._async_current_entries():
            if entry.source == config_entries.SOURCE_IMPORT:
                return self.async_abort(reason="no_mixed_config")

        self._errors = {}

        if user_input is not None:
            try:
                async with timeout(10):
                    gismeteo = _get_api_client(self.hass, user_input)
                    await gismeteo.async_update()
            except (TimeoutError, ApiError, ClientConnectorError, ClientError):
                self._errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self._show_config_form(user_input)

    def _show_config_form(self, config: ConfigType) -> config_entries.ConfigFlowResult:
        if config is None:
            config = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=config.get(CONF_NAME, self.hass.config.location_name),
                    ): str,
                    vol.Optional(
                        CONF_LATITUDE,
                        default=config.get(CONF_LATITUDE, self.hass.config.latitude),
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE,
                        default=config.get(CONF_LONGITUDE, self.hass.config.longitude),
                    ): cv.longitude,
                }
            ),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Get component options flow."""
        return GismeteoOptionsFlowHandler(config_entry)


class GismeteoOptionsFlowHandler(config_entries.OptionsFlow):
    """Gismeteo config flow options handler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: ConfigType = None  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:  # pylint: disable=unused-argument
        """Manage the options."""
        if self.config_entry.source == config_entries.SOURCE_IMPORT:
            return self.async_abort(reason="no_options_available")

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: ConfigType = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if CONF_FORECAST_DAYS in self.options:
                self.options[CONF_FORECAST_DAYS] = None
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_SHOW_ON_MAP,
                            default=self.options.get(CONF_SHOW_ON_MAP, False),
                        ): bool,
                        vol.Required(CONF_ADD_SENSORS, default=False): bool,
                        vol.Optional(CONF_FORECAST_DAYS): forecast_days_int,
                    }
                ),
                self.config_entry.options,
            ),
        )

    async def _update_options(self) -> config_entries.ConfigFlowResult:
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_NAME), data=self.options
        )
