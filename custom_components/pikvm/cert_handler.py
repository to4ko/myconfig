"""Async certificate and device verification helpers powered by pikvm-aio.

Hardware Certificate Architecture Note:
Stock PiKVM hardware appliances generate self-signed X.509 certificates at first
boot (via `kvmd-gencert`) that do not conform to RFC 5280 CA/leaf validation rules:
  - Missing BasicConstraints(CA=TRUE) extension when self-issued
  - Missing Subject Alternative Name (SAN) entries for LAN IP addresses
  - Generic Common Name (CN="localhost" or "pikvm")

Because strict OpenSSL 3.x X.509 path building and hostname verification reject
these certificates, `fetch_serialized_cert` captures the PEM-encoded leaf
certificate during setup/reconfiguration so the integration can:
  1. Detect new clients/appliances and verify that a TLS-enabled endpoint is reachable.
  2. Maintain encrypted TLS transport (`ssl_cert` passed to `PiKVMClient`) while
     bypassing standard CA-chain and hostname checks (`verify_ssl=False`,
     `check_hostname=False`).
"""

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
    """Fetch and serialize the remote PiKVM leaf certificate using pikvm-aio.

    Due to non-compliant PiKVM hardware certificates, the certificate is used to
    detect new clients/endpoints and ensure encrypted TLS transport rather than
    for standard CA-chain/hostname verification.
    """
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
    # WARNING (Non-Compliant Hardware Certificates):
    # PiKVM appliances ship with self-signed certificates lacking CA BasicConstraints
    # and IP SANs. We use the certificate to detect new clients and encrypt traffic
    # rather than to verify the host via CA chain. Therefore verify_ssl=False and
    # check_hostname=False are required here, while Home Assistant's shared session
    # (`inject-websession`) and pre-warmed SSLContext avoid blocking event-loop I/O.
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
        nested_serial = (
            device.get("hw", {}).get("platform", {}).get("serial")
            if hasattr(device, "get")
            else ""
        )
        serial = str(
            getattr(device, "serial", None) or nested_serial or "unknown"
        ).lower()
        model = str(getattr(device, "model", None) or "PiKVM")
        name = str(getattr(device, "name", None) or "PiKVM")
        return PiKVMResponse(True, model, serial, name, None)
    except PiKVMAuthenticationError:
        return PiKVMResponse(False, None, None, None, "Exception_HTTP403")
    except PiKVMTimeoutError:
        return PiKVMResponse(False, None, None, None, "timeout")
    except (PiKVMConnectionError, PiKVMDeviceError, Exception):  # noqa: BLE001
        return PiKVMResponse(False, None, None, None, "cannot_connect")
