"""Какой аккаунт Яндекса и какую запись Yandex Smart Home использует панель.

В Home Assistant может быть подключено несколько аккаунтов Яндекса (несколько
записей Яндекс.Станции) и несколько записей Yandex Smart Home. Выбор хранится в
настройках интеграции. Пока его нет, берётся первая запись — так панель работала
до появления выбора, и у кого аккаунт один, для них ничего не меняется.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_YAHA_ENTRY, CONF_YANDEX_ACCOUNT, DOMAIN, YAHA_DOMAIN, YS_DOMAIN


def station_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Аккаунты Яндекса — записи интеграции Яндекс.Станция."""
    return [
        entry
        for entry in hass.config_entries.async_entries(YS_DOMAIN)
        if not entry.disabled_by
    ]


def yaha_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Записи Yandex Smart Home."""
    return [
        entry
        for entry in hass.config_entries.async_entries(YAHA_DOMAIN)
        if not entry.disabled_by
    ]


def pick(entries: list[ConfigEntry], chosen: str | None) -> ConfigEntry | None:
    """Выбранная запись.

    Если выбранную удалили, подставляем другую, только когда выбирать не из чего:
    с несколькими аккаунтами молча взять чужой — значит править не тот дом.
    """
    if not entries:
        return None
    if not chosen:
        return entries[0]
    for entry in entries:
        if entry.entry_id == chosen:
            return entry
    return entries[0] if len(entries) == 1 else None


def _options(hass: HomeAssistant) -> Mapping[str, Any]:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0].options if entries else {}


def station_entry(hass: HomeAssistant) -> ConfigEntry | None:
    return pick(station_entries(hass), _options(hass).get(CONF_YANDEX_ACCOUNT))


def yaha_entry(hass: HomeAssistant) -> ConfigEntry | None:
    return pick(yaha_entries(hass), _options(hass).get(CONF_YAHA_ENTRY))


def account_key(hass: HomeAssistant) -> str:
    """Ключ аккаунта для слепков: логин не меняется, даже если запись добавить заново."""
    entry = station_entry(hass)
    if entry is None:
        return "_"
    return entry.unique_id or entry.entry_id
