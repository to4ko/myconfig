"""Utility functions for the PiKVM integration."""

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.helpers.translation import async_get_translations

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_TOTP,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def format_url(input_url):
    """Ensure the URL is properly formatted."""
    if not input_url.startswith("http"):
        input_url = f"https://{input_url}"
    return input_url.rstrip("/")


def create_data_schema(user_input):
    """Create the data schema for the form."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_USERNAME, default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
            ): str,
            vol.Required(
                CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            ): str,
            vol.Optional(CONF_TOTP, default=user_input.get(CONF_TOTP, "")): str
        }
    )


def update_existing_entry(hass: HomeAssistant | None, existing_entry, user_input):
    """Update an existing config entry."""
    updated_data = existing_entry.data.copy()
    updated_data.update(user_input)
    # Ensure the serial number is included in the updated data
    if "serial" not in updated_data:
        updated_data["serial"] = existing_entry.data.get("serial")
    if hass is not None:
        hass.config_entries.async_update_entry(existing_entry, data=updated_data)


def find_existing_entry(flow_handler, serial) -> config_entries.ConfigEntry | None:
    """Find an existing entry with the same serial number."""
    if not serial:
        return None
    
    existing_entries = flow_handler._async_current_entries()
    for entry in existing_entries:
        entry_serial = entry.data.get("serial")
        _LOGGER.debug("Checking existing %s against %s", entry_serial, serial)
        if entry_serial and entry_serial.lower() == serial.lower():
            return entry
    _LOGGER.debug("No existing entry found for %s, configuring", serial)
    return None


async def get_translations(hass: HomeAssistant, language, domain):
    """Get translations for the given language and domain."""
    if hass is None:
        raise ValueError("HomeAssistant instance cannot be None")
    translations = await async_get_translations(hass, language, "config")

    def translate(key, default):
        return translations.get(f"component.{domain}.{key}", default)

    return translate


def get_unique_id_base(config_entry, coordinator):
    """Generate the unique_id_base for the sensors."""
    serial = get_nested_value(coordinator.data, ["hw", "platform", "serial"], "unknown")
    return f"{config_entry.entry_id}_{serial}"


def get_nested_value(data, keys, default=None):
    """Safely get a nested value from a dictionary.

    :param data: The dictionary to search.
    :param keys: A list of keys to traverse the dictionary.
    :param default: The default value to return if the keys are not found.
    :return: The value found or the default value.
    """
    if data is None:
        return default
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data if data != {} else default


def bytes_to_mb(bytes_value):
    """Convert bytes to megabytes.

    :param bytes_value: The value in bytes.
    :return: The value in megabytes.
    """
    return bytes_value / (1024 * 1024)