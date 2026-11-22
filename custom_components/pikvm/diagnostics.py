"""Diagnostics for PiKVM integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import PiKVMConfigEntry
from .const import CONF_CERTIFICATE, CONF_PASSWORD, CONF_TOTP
from .utils import extract_raw_dict

TO_REDACT = {
    CONF_PASSWORD,
    CONF_TOTP,
    CONF_CERTIFICATE,
    "password",
    "totp",
    "totp_secret",
    "tls-certificate",
    "certificate",
    "cert",
    "secret",
    "token",
    "access_token",
    "auth_token",
    "api_key",
    "private_key",
    "secret_key",
    "encryption_key",
    "session_key",
    "auth_key",
    "access_key",
    "session_id",
    "authorization",
    "jwt",
    "cookie",
    "cookies",
    "pin",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PiKVMConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = getattr(config_entry, "runtime_data", None)
    coordinator_data = (
        extract_raw_dict(coordinator.data) or None
        if coordinator and coordinator.data is not None
        else None
    )

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "data": (
                async_redact_data(coordinator_data, TO_REDACT)
                if coordinator_data
                else None
            ),
        }
        if coordinator
        else {},
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: PiKVMConfigEntry,
    device: dr.DeviceEntry,
) -> dict[str, Any]:
    """Return redacted diagnostics for a device."""
    entry_diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    return {
        **entry_diagnostics,
        "device": async_redact_data(device.dict_repr, TO_REDACT),
    }
