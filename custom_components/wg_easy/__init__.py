from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    API_VERSION_V15,
    CONF_API_VERSION,
    CONF_ONLINE_TIMEOUT_MINUTES,
    CONF_ONLINE_TIMEOUT_SECONDS,
    CONF_RESOLVED_API_VERSION,
    CONF_VERIFY_SSL,
    DEFAULT_ONLINE_TIMEOUT_MINUTES,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import WGEasyCoordinator

_LOGGER = logging.getLogger(__name__)


type WGEasyConfigEntry = ConfigEntry[WGEasyCoordinator]


def _migrate_online_timeout_option(hass: HomeAssistant, entry: WGEasyConfigEntry) -> None:
    """One-time, automatic migration of the online-timeout option from minutes to seconds.

    Existing installs stored this as an integer number of minutes under
    ``online_timeout_minutes``. Newer versions use ``online_timeout_seconds``
    instead. If an entry still only has the legacy key, convert it in place
    (minutes * 60) so behaviour is unchanged for the user and no manual
    reconfiguration is required.
    """
    if CONF_ONLINE_TIMEOUT_SECONDS in entry.options:
        return

    legacy_minutes = entry.options.get(
        CONF_ONLINE_TIMEOUT_MINUTES, DEFAULT_ONLINE_TIMEOUT_MINUTES
    )
    new_options = {
        key: value
        for key, value in entry.options.items()
        if key != CONF_ONLINE_TIMEOUT_MINUTES
    }
    new_options[CONF_ONLINE_TIMEOUT_SECONDS] = int(legacy_minutes) * 60

    hass.config_entries.async_update_entry(entry, options=new_options)
    _LOGGER.info(
        "WG Easy (%s): migrated online timeout option from %s minute(s) to %s second(s)",
        entry.title,
        legacy_minutes,
        new_options[CONF_ONLINE_TIMEOUT_SECONDS],
    )


def _migrate_api_version_data(hass: HomeAssistant, entry: WGEasyConfigEntry) -> None:
    """One-time migration for entries created before v14 support existed.

    Those entries always spoke the v15 (bearer-token) API and have no
    api_version/resolved_api_version keys yet. Fill them in explicitly so
    behaviour is unchanged and no reconfiguration is required.
    """
    if CONF_API_VERSION in entry.data:
        return

    new_data = {
        **entry.data,
        CONF_API_VERSION: API_VERSION_V15,
        CONF_RESOLVED_API_VERSION: API_VERSION_V15,
    }
    hass.config_entries.async_update_entry(entry, data=new_data)
    _LOGGER.info(
        "WG Easy (%s): migrated existing entry to explicit v15 API mode",
        entry.title,
    )


def _migrate_verify_ssl_data(hass: HomeAssistant, entry: WGEasyConfigEntry) -> None:
    """One-time migration for entries created before the SSL-verification

    toggle existed. Defaults to True (verify), matching the behaviour those
    entries already had (Home Assistant's shared aiohttp session verifies
    certificates by default), so nothing changes for existing users.
    """
    if CONF_VERIFY_SSL in entry.data:
        return

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL}
    )
    _LOGGER.info(
        "WG Easy (%s): migrated existing entry to explicit verify_ssl=%s",
        entry.title,
        DEFAULT_VERIFY_SSL,
    )


async def async_setup_entry(hass: HomeAssistant, entry: WGEasyConfigEntry) -> bool:
    _migrate_online_timeout_option(hass, entry)
    _migrate_api_version_data(hass, entry)
    _migrate_verify_ssl_data(hass, entry)

    coordinator = WGEasyCoordinator(
        hass,
        config_entry_id=entry.entry_id,
        url=entry.data[CONF_URL],
        api_version=entry.data[CONF_RESOLVED_API_VERSION],
        token=entry.data.get(CONF_TOKEN),
        password=entry.data.get(CONF_PASSWORD),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        poll_interval=entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to WG Easy: {err}") from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WGEasyConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: WGEasyConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    coordinator = entry.runtime_data
    active_client_keys = {
        client["publicKey"] for client in coordinator.data.get("clients", [])
    }

    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN and identifier[1] in active_client_keys
    )
