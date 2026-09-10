"""The PiKVM integration."""

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .cert_handler import format_url
from .const import (
    CONF_CERTIFICATE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SERIAL,
    CONF_USERNAME,
    CONF_TOTP,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import PiKVMDataUpdateCoordinator
from .entity import PiKVMEntity
from .utils import get_nested_value

_LOGGER = logging.getLogger(__name__)

# Define a minimal CONFIG_SCHEMA
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.url,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
                vol.Optional(CONF_TOTP, default=""): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PiKVM component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PiKVM from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Retrieve the unique ID and serial number from the config entry
    stored_serial = entry.data.get(CONF_SERIAL)
    unique_id = entry.unique_id

    # Check if the unique ID matches the stored serial number
    if stored_serial and unique_id != stored_serial:
        _LOGGER.debug("Updating unique ID from %s to %s", unique_id, stored_serial)
        hass.config_entries.async_update_entry(entry, unique_id=stored_serial)

    coordinator = PiKVMDataUpdateCoordinator(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_TOTP, ""),
        entry.data[CONF_CERTIFICATE],
    )
    
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Retrieve hardware and system information safely
    platform = get_nested_value(coordinator.data, ["hw", "platform"], {})
    kvmd = get_nested_value(coordinator.data, ["system", "kvmd"], {})

    coordinator.device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_SERIAL])},
        configuration_url=format_url(entry.data[CONF_HOST]),
        serial_number=entry.data[CONF_SERIAL],
        manufacturer=MANUFACTURER,
        name=entry.title,
        model=platform.get("model") or platform.get("type"),
        hw_version=platform.get("base"),
        sw_version=kvmd.get("version"),
    )

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Clean up orphaned devices that were created by previous versions
    await _async_cleanup_devices(hass, entry)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def _async_cleanup_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove devices that have no entities and belong to this config entry."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in devices:
        entities = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
        if not entities:
            _LOGGER.info("Removing orphaned PiKVM device: %s", device.name)
            dev_reg.async_remove_device(device.id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.data[DOMAIN].pop(entry.entry_id, None)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry."""
    # Forward the entry removal signal to the 'sensor' component
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    # Remove the entry from the 'pikvm' domain data
    hass.data[DOMAIN].pop(entry.entry_id, None)