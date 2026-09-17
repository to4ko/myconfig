"""Настройка интеграции: одна кнопка при установке и пункт меню в настройках."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import CONF_SHOW_IN_SIDEBAR, DOMAIN, PANEL_TITLE, YS_DOMAIN


class YandexDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Проверяем, что есть Яндекс.Станция, и создаём запись."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return YandexMenuOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if not self.hass.config_entries.async_entries(YS_DOMAIN):
            return self.async_abort(reason="no_yandex_station")

        if user_input is not None:
            return self.async_create_entry(title=PANEL_TITLE, data={})

        return self.async_show_form(step_id="user")


class YandexMenuOptionsFlow(OptionsFlow):
    """Показывать ли «Яндекс меню» в левом меню."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        # handler у настроек — id записи; так работает и на старых версиях HA
        entry = self.hass.config_entries.async_get_entry(self.handler)
        current = entry.options.get(CONF_SHOW_IN_SIDEBAR, True) if entry else True
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_SHOW_IN_SIDEBAR, default=current): bool}
            ),
        )
