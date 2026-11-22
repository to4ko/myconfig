"""Utility functions for the PiKVM integration."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pikvm_aio import PiKVMDeviceInfo, format_url

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SERIAL,
    CONF_TOTP,
    CONF_USERNAME,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
)

_SENTINEL = object()

normalize_url = format_url


def ensure_device_info(data: Any) -> PiKVMDeviceInfo | None:
    """Return a PiKVMDeviceInfo instance from a model or dictionary."""
    if isinstance(data, PiKVMDeviceInfo):
        return data
    if isinstance(data, Mapping):
        try:
            return PiKVMDeviceInfo.from_dict(dict(data))
        except Exception:  # noqa: BLE001
            return None
    return None


def extract_raw_dict(data: Any) -> dict[str, Any]:
    """Extract raw dictionary payload from a PiKVMDeviceInfo or mapping."""
    raw = getattr(data, "raw", None)
    if isinstance(raw, dict):
        return raw
    return data if isinstance(data, dict) else {}


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
    return None if not cleaned or cleaned in ("none", "unknown") else cleaned


def update_existing_entry(
    hass: HomeAssistant | None,
    existing_entry: config_entries.ConfigEntry,
    user_input: Mapping[str, Any],
) -> None:
    """Update an existing config entry."""
    updated_data = {**existing_entry.data, **user_input}
    norm_serial = normalize_serial(
        updated_data.get(CONF_SERIAL)
        or existing_entry.data.get(CONF_SERIAL)
        or getattr(existing_entry, "unique_id", None)
    )
    updated_data[CONF_SERIAL] = norm_serial or existing_entry.data.get(CONF_SERIAL)
    if hass is not None:
        if norm_serial and getattr(existing_entry, "unique_id", None) != norm_serial:
            hass.config_entries.async_update_entry(
                existing_entry, data=updated_data, unique_id=norm_serial
            )
        else:
            hass.config_entries.async_update_entry(existing_entry, data=updated_data)


def find_existing_entry(
    flow_handler: Any, serial: str | None
) -> config_entries.ConfigEntry | None:
    """Find an existing entry with the same serial number."""
    if not (norm_serial := normalize_serial(serial)):
        return None
    existing_entries: list[config_entries.ConfigEntry] = (
        flow_handler._async_current_entries()
    )
    for entry in existing_entries:
        entry_serial = normalize_serial(
            entry.data.get(CONF_SERIAL)
        ) or normalize_serial(getattr(entry, "unique_id", None))
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
        entry_data.get(CONF_SERIAL) if isinstance(entry_data, Mapping) else None,
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
    if data is None or not isinstance(keys, (str, Sequence)):
        return default
    for key in [keys] if isinstance(keys, str) else keys:
        if not (isinstance(data, Mapping) or hasattr(data, "get")):
            return default
        try:
            if (data := data.get(key, _SENTINEL)) is _SENTINEL:
                return default
        except Exception:  # noqa: BLE001
            return default
    return data


def bytes_to_mb(bytes_value: Any) -> float | None:
    """Convert bytes to megabytes."""
    try:
        val = float(bytes_value)
        return val / (1024 * 1024) if math.isfinite(val) else None
    except (ValueError, TypeError, OverflowError):
        return None
