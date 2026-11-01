"""Utility functions for the PiKVM integration."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOTP,
    CONF_USERNAME,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
)

_LOGGER = logging.getLogger(__name__)
_SENTINEL = object()


def normalize_url(input_url: str) -> str:
    """Ensure the URL is properly formatted."""
    url = input_url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


format_url = normalize_url


def create_data_schema(user_input: Mapping[str, Any] | None = None) -> vol.Schema:
    """Create the data schema for the form."""
    input_data = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=input_data.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_USERNAME, default=input_data.get(CONF_USERNAME, DEFAULT_USERNAME)
            ): str,
            vol.Required(
                CONF_PASSWORD, default=input_data.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            ): str,
            vol.Optional(CONF_TOTP, default=input_data.get(CONF_TOTP, "")): str,
        }
    )


def normalize_serial(serial: Any) -> str | None:
    """Normalize a PiKVM hardware serial number."""
    if not isinstance(serial, str):
        return None
    cleaned = serial.strip().lower()
    if not cleaned or cleaned in ("none", "unknown"):
        return None
    return cleaned


def update_existing_entry(
    hass: HomeAssistant | None,
    existing_entry: config_entries.ConfigEntry,
    user_input: Mapping[str, Any],
) -> None:
    """Update an existing config entry."""
    updated_data = dict(existing_entry.data)
    updated_data.update(user_input)
    raw_serial = (
        updated_data.get("serial")
        or existing_entry.data.get("serial")
        or getattr(existing_entry, "unique_id", None)
    )
    norm_serial = normalize_serial(raw_serial)
    updated_data["serial"] = (
        norm_serial if norm_serial is not None else existing_entry.data.get("serial")
    )
    if hass is not None:
        unique_id_arg = (
            norm_serial
            if norm_serial and getattr(existing_entry, "unique_id", None) != norm_serial
            else None
        )
        if unique_id_arg is not None:
            hass.config_entries.async_update_entry(
                existing_entry, data=updated_data, unique_id=unique_id_arg
            )
        else:
            hass.config_entries.async_update_entry(existing_entry, data=updated_data)


def find_existing_entry(
    flow_handler: Any, serial: str | None
) -> config_entries.ConfigEntry | None:
    """Find an existing entry with the same serial number."""
    norm_serial = normalize_serial(serial)
    if not norm_serial:
        return None

    existing_entries: list[config_entries.ConfigEntry] = (
        flow_handler._async_current_entries()
    )
    for entry in existing_entries:
        entry_serial = normalize_serial(entry.data.get("serial")) or normalize_serial(
            getattr(entry, "unique_id", None)
        )
        if entry_serial == norm_serial:
            return entry
    return None


def get_unique_id_base(
    config_entry: Any,
    coordinator: Any = None,
) -> str:
    """Generate the unique_id_base for entities."""
    coord_data = getattr(coordinator, "data", None)
    entry_data = getattr(config_entry, "data", None)
    for candidate in (
        get_nested_value(coord_data, ["hw", "platform", "serial"]),
        entry_data.get("serial") if isinstance(entry_data, Mapping) else None,
        getattr(config_entry, "unique_id", None),
    ):
        if (
            isinstance(candidate, (str, int))
            and not isinstance(candidate, bool)
            and (cleaned := str(candidate).strip())
            and cleaned.lower() != "none"
        ):
            return f"{config_entry.entry_id}_{cleaned}"
    return f"{config_entry.entry_id}_unknown"


def get_nested_value(
    data: Any,
    keys: Sequence[str] | str,
    default: Any = None,
) -> Any:
    """Safely get a nested value from a dictionary or mapping."""
    if data is None or keys is None:
        return default
    if isinstance(keys, str):
        key_list: Sequence[Any] = [keys]
    elif isinstance(keys, Sequence):
        key_list = keys
    else:
        return default

    for key in key_list:
        if isinstance(data, Mapping) or hasattr(data, "get"):
            try:
                data = data.get(key, _SENTINEL)
                if data is _SENTINEL:
                    return default
            except Exception:  # noqa: BLE001
                return default
        else:
            return default
    return data


def bytes_to_mb(bytes_value: Any) -> float | None:
    """Convert bytes to megabytes."""
    if bytes_value is None:
        return None
    try:
        val = float(bytes_value)
        if not math.isfinite(val):
            return None
        return val / (1024 * 1024)
    except (ValueError, TypeError, OverflowError):
        return None
