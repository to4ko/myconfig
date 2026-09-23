"""Настройка интеграции: установка в одну кнопку, в настройках — аккаунт и пункт меню."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .accounts import station_entries, yaha_entries
from .const import (
    CONF_SHOW_IN_SIDEBAR,
    CONF_YAHA_ENTRY,
    CONF_YANDEX_ACCOUNT,
    DOMAIN,
    PANEL_TITLE,
    YS_DOMAIN,
)


def _account_fields(hass: HomeAssistant, current: Mapping[str, Any]) -> dict[Any, Any]:
    """Выбор аккаунта и записи Yandex Smart Home — только когда есть из чего выбирать."""
    fields: dict[Any, Any] = {}
    for key, entries in (
        (CONF_YANDEX_ACCOUNT, station_entries(hass)),
        (CONF_YAHA_ENTRY, yaha_entries(hass)),
    ):
        if len(entries) < 2:
            continue
        ids = [entry.entry_id for entry in entries]
        default = current.get(key) if current.get(key) in ids else ids[0]
        fields[vol.Required(key, default=default)] = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=entry.entry_id, label=entry.title)
                    for entry in entries
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
    return fields


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
            return self.async_create_entry(title=PANEL_TITLE, data={}, options=user_input)

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(_account_fields(self.hass, {}))
        )


class YandexMenuOptionsFlow(OptionsFlow):
    """Аккаунт Яндекса (если их несколько) и пункт в левом меню."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        # handler у настроек — id записи; так работает и на старых версиях HA
        entry = self.hass.config_entries.async_get_entry(self.handler)
        options = entry.options if entry else {}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    **_account_fields(self.hass, options),
                    vol.Required(
                        CONF_SHOW_IN_SIDEBAR,
                        default=options.get(CONF_SHOW_IN_SIDEBAR, True),
                    ): bool,
                }
            ),
        )
