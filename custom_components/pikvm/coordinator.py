"""Manages fetching data from the PiKVM API."""

from __future__ import annotations

import logging
import ssl
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pikvm_aio import (
    PiKVMAuthenticationError,
    PiKVMClient,
    PiKVMConnectionError,
    PiKVMDeviceError,
    PiKVMDeviceInfo,
    PiKVMError,
    PiKVMTimeoutError,
    format_url,
    parse_host_port,
)

from .cert_handler import _DEFAULT_NO_VERIFY_SSL_CONTEXT
from .const import DOMAIN
from .utils import get_nested_value

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 30


class PiKVMDataUpdateCoordinator(DataUpdateCoordinator[PiKVMDeviceInfo]):
    """Class to manage fetching data from the PiKVM API asynchronously."""

    url: str = ""
    device_info: DeviceInfo | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        username: str,
        password: str,
        totp: str,
        cert: str,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.url = format_url(url)
        self.username = username
        self.password = password
        self.totp = totp
        self.cert = cert
        self.device_info = None

        try:
            self.clean_host = parse_host_port(self.url)[0]
        except Exception:  # noqa: BLE001
            self.clean_host = self.url.replace("https://", "").replace("http://", "").split("/")[0]

        scan_interval = DEFAULT_SCAN_INTERVAL
        if entry is not None:
            scan_interval = entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

        self.client = PiKVMClient(
            host=self.url,
            username=self.username,
            password=self.password,
            totp_secret=self.totp if self.totp else None,
            session=async_get_clientsession(hass),
            ssl_cert=self.cert if self.cert else None,
            verify_ssl=False,
            check_hostname=False,
            ssl_context=_DEFAULT_NO_VERIFY_SSL_CONTEXT,
        )

    @property
    def device_name(self) -> str:
        """Return the friendly device name for UI display and repair issues."""
        raw_name: str | None = None
        if self.config_entry:
            dev_reg = dr.async_get(self.hass)
            devices = dr.async_entries_for_config_entry(dev_reg, self.config_entry.entry_id)
            for dev in devices:
                if dev.name_by_user:
                    return dev.name_by_user
                if dev.name:
                    raw_name = dev.name
                    break
            if not raw_name and self.config_entry.title:
                raw_name = self.config_entry.title

        if not raw_name and self.device_info and self.device_info.get("name"):
            raw_name = str(self.device_info["name"])

        if not raw_name and self.data and getattr(self.data, "name", None):
            data_name = self.data.name
            if data_name and data_name not in ("localhost", "localhost.localdomain"):
                raw_name = str(data_name)

        if not raw_name:
            return "PiKVM"

        # Strip legacy clean_host suffix if present (e.g. "PiKVM (192.168.1.50)" -> "PiKVM")
        host_suffix = f" ({self.clean_host})"
        if self.clean_host and raw_name.endswith(host_suffix):
            cleaned = raw_name[: -len(host_suffix)].strip()
            if cleaned:
                return cleaned

        return raw_name

    def _async_check_hardware_health(self, data: Any) -> None:
        """Monitor hardware undervoltage and throttling issues."""
        entry_id = self.config_entry.entry_id if self.config_entry else self.clean_host
        if not entry_id:
            return

        raw_data = getattr(data, "raw", None)
        if not isinstance(raw_data, dict):
            raw_data = data if isinstance(data, dict) else {}

        throttling = get_nested_value(raw_data, ["hw", "health", "throttling"], {})
        if not isinstance(throttling, dict):
            throttling = {}
        raw_flags = get_nested_value(throttling, ["raw_flags"], 0) or 0
        text_flags = get_nested_value(throttling, ["text_flags"], [])
        if not isinstance(text_flags, (list, tuple, set)):
            text_flags = []
        voltage_core = get_nested_value(throttling, ["voltage", "core"], {})
        if not isinstance(voltage_core, dict):
            voltage_core = {}

        is_under_voltage_now = bool(
            voltage_core.get("now")
            or (isinstance(raw_flags, int) and (raw_flags & 0x1))
            or ("under-voltage" in text_flags)
        )
        is_under_voltage_past = bool(
            voltage_core.get("past")
            or (isinstance(raw_flags, int) and (raw_flags & 0x10000))
        )
        has_under_voltage = is_under_voltage_now or is_under_voltage_past

        is_throttled_now = bool(
            (isinstance(raw_flags, int) and (raw_flags & 0x6))
            or ("throttled" in text_flags)
            or ("arm-frequency-capped" in text_flags)
        )
        is_throttled_past = bool(
            isinstance(raw_flags, int) and (raw_flags & 0x60000)
        )
        has_throttling = is_throttled_now or is_throttled_past

        # Undervoltage Issue Management
        uv_issue_id = f"undervoltage_{entry_id}"
        if has_under_voltage:
            async_create_issue(
                self.hass,
                DOMAIN,
                uv_issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=IssueSeverity.CRITICAL if is_under_voltage_now else IssueSeverity.WARNING,
                translation_key="undervoltage",
                translation_placeholders={"device_name": self.device_name},
                learn_more_url="https://docs.pikvm.org/power/",
            )
        else:
            async_delete_issue(self.hass, DOMAIN, uv_issue_id)

        # Throttling Issue Management
        th_issue_id = f"throttling_{entry_id}"
        if has_throttling:
            async_create_issue(
                self.hass,
                DOMAIN,
                th_issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=IssueSeverity.WARNING,
                translation_key="throttling",
                translation_placeholders={"device_name": self.device_name},
                learn_more_url="https://docs.pikvm.org/",
            )
        else:
            async_delete_issue(self.hass, DOMAIN, th_issue_id)

    async def _async_update_data(self) -> PiKVMDeviceInfo:
        """Fetch data from PiKVM API."""
        try:
            _LOGGER.debug("Fetching PiKVM Info & MSD from %s", self.url)
            data = await self.client.get_info()
            self._async_check_hardware_health(data)
            return data
        except PiKVMAuthenticationError as auth_err:
            _LOGGER.debug("Authentication failed for PiKVM at %s: %s", self.url, auth_err)
            raise ConfigEntryAuthFailed(
                "Invalid credentials or 2FA TOTP token required",
                translation_domain=DOMAIN,
                translation_key="authentication_error",
                translation_placeholders={"host": self.clean_host},
            ) from auth_err
        except (TimeoutError, PiKVMTimeoutError) as err:
            _LOGGER.debug("Timeout connecting to PiKVM at %s: %s", self.url, err)
            raise UpdateFailed(
                f"Connection timed out reaching {self.clean_host}",
                translation_domain=DOMAIN,
                translation_key="timeout",
                translation_placeholders={"host": self.clean_host},
            ) from err
        except ssl.SSLError as err:
            _LOGGER.debug("SSL error connecting to PiKVM at %s: %s", self.url, err)
            raise UpdateFailed(
                f"SSL certificate validation failed for {self.clean_host}",
                translation_domain=DOMAIN,
                translation_key="ssl_certificate_error",
                translation_placeholders={"host": self.clean_host},
            ) from err
        except (PiKVMConnectionError, aiohttp.ClientError, OSError) as err:
            _LOGGER.debug("Connection error to PiKVM at %s: %s", self.url, err)
            raise UpdateFailed(
                f"Cannot connect to {self.clean_host} (host offline or connection refused)",
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.clean_host},
            ) from err
        except (PiKVMDeviceError, PiKVMError) as err:
            clean_err = (
                " ".join(str(err).split()).split("<html")[0].rstrip(": ").strip()
                or str(err)
            )
            _LOGGER.debug(
                "Error communicating with PiKVM API at %s: %s", self.url, clean_err
            )
            raise UpdateFailed(
                f"Error communicating with PiKVM at {self.clean_host}: {clean_err}",
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "host": self.clean_host,
                    "error": clean_err,
                },
            ) from err
