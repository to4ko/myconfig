"""Async certificate and device verification helpers powered by pikvm-aio."""

from __future__ import annotations

import logging
import ssl
from typing import NamedTuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pikvm_aio import (
    PiKVMAuthenticationError,
    PiKVMClient,
    PiKVMConnectionError,
    PiKVMDeviceError,
    PiKVMTimeoutError,
    fetch_remote_cert,
)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_NO_VERIFY_SSL_CONTEXT: ssl.SSLContext | None
try:
    from homeassistant.util.ssl import get_default_no_verify_context

    _DEFAULT_NO_VERIFY_SSL_CONTEXT = get_default_no_verify_context()
except Exception:  # noqa: BLE001
    _DEFAULT_NO_VERIFY_SSL_CONTEXT = None


class PiKVMResponse(NamedTuple):
    """Response returned by is_pikvm_device verification helper."""

    success: bool
    model: str | None
    serial: str | None
    name: str | None
    error: str | None


async def fetch_serialized_cert(hass: HomeAssistant | None, url: str) -> str | None:
    """Fetch and serialize certificate using pikvm-aio."""
    try:
        return await fetch_remote_cert(url, timeout=5.0)
    except Exception as e:  # noqa: BLE001
        _LOGGER.debug("Could not fetch certificate from %s: %s", url, e)
        return None


async def is_pikvm_device(
    hass: HomeAssistant | None, url: str, username: str, password: str, cert: str
) -> PiKVMResponse:
    """Check if the device is a PiKVM and return its properties."""
    session = async_get_clientsession(hass) if hass else None
    client = PiKVMClient(
        host=url,
        username=username,
        password=password,
        session=session,
        ssl_cert=cert,
        verify_ssl=False,
        check_hostname=False,
        timeout=5.0,
        ssl_context=_DEFAULT_NO_VERIFY_SSL_CONTEXT,
    )
    try:
        device = await client.get_info()
        serial = str(getattr(device, "serial", None) or (device.get("hw", {}).get("platform", {}).get("serial") if hasattr(device, "get") else "") or "unknown").lower()
        model = str(getattr(device, "model", None) or "PiKVM")
        name = str(getattr(device, "name", None) or "PiKVM")
        return PiKVMResponse(True, model, serial, name, None)
    except PiKVMAuthenticationError:
        return PiKVMResponse(False, None, None, None, "Exception_HTTP403")
    except PiKVMTimeoutError:
        return PiKVMResponse(False, None, None, None, "timeout")
    except (PiKVMConnectionError, PiKVMDeviceError):
        return PiKVMResponse(False, None, None, None, "cannot_connect")
    except Exception:  # noqa: BLE001
        return PiKVMResponse(False, None, None, None, "cannot_connect")
