#  Copyright (c) 2019-2024, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
"""
The Gismeteo component.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""

import logging
from functools import cached_property

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientConnectorError
from async_timeout import timeout
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DOMAIN,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    _DataT,
)

from .api import ApiError, GismeteoApiClient
from .const import (
    CONF_ADD_SENSORS,
    CONF_CACHE_DIR,
    CONF_CACHE_TIME,
    CONF_FORECAST_DAYS,
    CONF_TIMEZONE,
    COORDINATOR,
    DOMAIN,
    DOMAIN_YAML,
    PLATFORMS,
    STARTUP_MESSAGE,
    UNDO_UPDATE_LISTENER,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


forecast_days_int = vol.All(vol.Coerce(int), vol.Range(min=0, max=6))

LOCATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
        vol.Optional(CONF_SENSORS): cv.deprecated,
        vol.Optional(CONF_ADD_SENSORS, default=False): cv.boolean,
        vol.Optional(CONF_FORECAST_DAYS): forecast_days_int,
        vol.Optional(CONF_CACHE_DIR): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(vol.Any(LOCATION_SCHEMA, None))},
    extra=vol.ALLOW_EXTRA,
)


def deslugify(text: str) -> str:
    """Deslugify string."""
    return text.replace("_", " ").capitalize()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up component."""
    if DOMAIN not in hass.data:
        _LOGGER.info(STARTUP_MESSAGE)
        hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    hass.data[DOMAIN_YAML] = config[DOMAIN]
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )

    return True


def _get_api_client(
    hass: HomeAssistant, config: ConfigType | None
) -> GismeteoApiClient:
    """Prepare Gismeteo API client instance."""
    if config is None:
        config = {}
    return GismeteoApiClient(
        async_get_clientsession(hass),
        latitude=config.get(CONF_LATITUDE, hass.config.latitude),
        longitude=config.get(CONF_LONGITUDE, hass.config.longitude),
        params={
            CONF_DOMAIN: DOMAIN,
            CONF_TIMEZONE: str(hass.config.time_zone),
            CONF_CACHE_DIR: config.get(CONF_CACHE_DIR, hass.config.path(STORAGE_DIR)),
            CONF_CACHE_TIME: UPDATE_INTERVAL.total_seconds(),
            CONF_SHOW_ON_MAP: config.get(CONF_SHOW_ON_MAP, False),
        },
    )


async def _async_get_coordinator(
    hass: HomeAssistant, unique_id: str | None, config: dict
) -> DataUpdateCoordinator:
    """Prepare update coordinator instance."""
    gismeteo = _get_api_client(hass, config)
    await gismeteo.async_update_location()

    coordinator = GismeteoDataUpdateCoordinator(hass, unique_id, gismeteo)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    return coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gismeteo as config entry."""
    if entry.source == SOURCE_IMPORT:
        # Setup from configuration.yaml
        for uid, config in hass.data[DOMAIN_YAML].items():
            coordinator = await _async_get_coordinator(hass, uid, config)
            hass.data[DOMAIN][uid] = {
                COORDINATOR: coordinator,
            }

        undo_listener = entry.add_update_listener(update_listener)
        hass.data[DOMAIN][entry.entry_id] = {
            UNDO_UPDATE_LISTENER: undo_listener,
        }

    else:
        # Setup from config entry
        config = entry.data.copy()  # type: ConfigType
        config.update(entry.options)

        coordinator = await _async_get_coordinator(hass, entry.entry_id, config)
        undo_listener = entry.add_update_listener(update_listener)
        hass.data[DOMAIN][entry.entry_id] = {
            COORDINATOR: coordinator,
            UNDO_UPDATE_LISTENER: undo_listener,
        }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


class GismeteoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gismeteo data API."""

    def __init__(
        self, hass: HomeAssistant, unique_id: str | None, gismeteo: GismeteoApiClient
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

        self.gismeteo = gismeteo
        self._unique_id = unique_id

    @cached_property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    async def _async_update_data(self) -> _DataT:
        """Update data via library."""
        try:
            async with timeout(10):
                await self.gismeteo.async_update()
        except (ApiError, ClientConnectorError) as error:
            raise UpdateFailed(error) from error
        else:
            return self.gismeteo.current_data
