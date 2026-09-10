"""Diagnostics for PiKVM integration."""

from collections.abc import Mapping
import json
import logging
from threading import Lock
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)

    diagnostics_data = {
        "config_entry": _mask_sensitive_data(_expand_mapping_proxy(vars(config_entry))),
        "coordinator": {
            "last_update_success": coordinator.last_update_success
            if coordinator
            else None,
            "update_interval": str(coordinator.update_interval)
            if coordinator
            else None,
            "states": _mask_sensitive_data(_expand_mapping_proxy(coordinator.data))
            if coordinator
            else {},
        }
        if coordinator
        else {},
    }

    # Sanitize diagnostics data before serialization
    sanitized_data = _sanitize_data(diagnostics_data)

    # Pretty-print the diagnostics data
    try:
        pretty_diagnostics = json.dumps(
            {config_entry.entry_id: sanitized_data},
            indent=4,
            default=_default_json_serialize,
        )
        _LOGGER.debug("Diagnostics data: %s", pretty_diagnostics)
    except TypeError as e:
        _LOGGER.error("Failed to serialize diagnostics data: %s", e)

    return sanitized_data


def _mask_sensitive_data(data):
    """Mask sensitive data such as passwords."""
    if not data:
        return data

    def mask_item(item):
        """Masks sensitive data in a single item."""
        if isinstance(item, dict):
            return {k: "******" if "password" in k else v for k, v in item.items()}
        if isinstance(item, list):
            return [mask_item(i) for i in item]
        if isinstance(item, MappingProxyType):
            return mask_item(dict(item))
        return item

    return mask_item(data)


def _expand_mapping_proxy(data):
    """Expand a mapping proxy to a dictionary."""
    if isinstance(data, MappingProxyType):
        return dict(data)
    if isinstance(data, dict):
        return {k: _expand_mapping_proxy(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_mapping_proxy(item) for item in data]
    return data


def _default_json_serialize(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, MappingProxyType):
        return dict(obj)
    if isinstance(obj, ConfigEntryState):
        return obj.name
    if isinstance(obj, Lock):
        return "Lock"
    if callable(obj):
        return None  # Skip functions
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _sanitize_data(data):
    """Sanitize data by removing non-serializable types."""
    if isinstance(data, dict):
        return {k: _sanitize_data(v) for k, v in data.items() if not callable(v)}
    if isinstance(data, list):
        return [_sanitize_data(i) for i in data if not callable(i)]
    return data
