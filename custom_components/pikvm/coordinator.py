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
from pikvm_aio.models import ThrottlingInfo

from .cert_handler import _DEFAULT_NO_VERIFY_SSL_CONTEXT
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .utils import ensure_device_info

_LOGGER = logging.getLogger(__name__)


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
            self.clean_host = (
                self.url.replace("https://", "").replace("http://", "").split("/")[0]
            )

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

        # WARNING (Non-Compliant Hardware Certificates):
        # Stock PiKVM hardware generates a self-signed X.509 certificate at first boot
        # (via kvmd-gencert) with CN="localhost", no IP Subject Alternative Names (SANs),
        # and no CA BasicConstraints. OpenSSL 3.x / RFC 5280 strictly rejects these certs
        # during standard CA/hostname verification. We therefore store the certificate to
        # detect new clients/appliances and keep TLS transport encryption active, while
        # explicitly setting verify_ssl=False and check_hostname=False and injecting
        # Home Assistant's shared aiohttp ClientSession (Platinum rule `inject-websession`).
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
            for dev in dr.async_entries_for_config_entry(
                dev_reg, self.config_entry.entry_id
            ):
                if dev.name_by_user:
                    return dev.name_by_user
                if dev.name:
                    raw_name = dev.name
                    break
            if not raw_name and self.config_entry.title:
                raw_name = self.config_entry.title

        if not raw_name and self.device_info and self.device_info.get("name"):
            raw_name = str(self.device_info["name"])

        if (
            not raw_name
            and self.data
            and getattr(self.data, "name", None)
            and (data_name := str(self.data.name))
            not in ("localhost", "localhost.localdomain")
        ):
            raw_name = data_name

        if not raw_name:
            return "PiKVM"

        host_suffix = f" ({self.clean_host})"
        if (
            self.clean_host
            and raw_name.endswith(host_suffix)
            and (cleaned := raw_name[: -len(host_suffix)].strip())
        ):
            return cleaned
        return raw_name

    def _sync_repair_issue(
        self,
        issue_id: str,
        is_active: bool,
        severity: IssueSeverity,
        translation_key: str,
        learn_more_url: str,
    ) -> None:
        """Create or delete a Home Assistant Repairs issue."""
        if is_active:
            async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders={"device_name": self.device_name},
                learn_more_url=learn_more_url,
            )
        else:
            async_delete_issue(self.hass, DOMAIN, issue_id)

    def _async_check_hardware_health(self, data: Any) -> None:
        """Monitor hardware undervoltage and throttling issues using ThrottlingInfo."""
        entry_id = (
            self.config_entry.entry_id if self.config_entry else self.clean_host
        )
        if not entry_id:
            return

        info = ensure_device_info(data)
        throttling = info.hw.health.throttling if info else ThrottlingInfo()

        flags = throttling.raw_flags
        text_flags = throttling.text_flags

        is_under_voltage_now = bool(
            throttling.undervoltage_now
            or (flags & 0x1)
            or ("under-voltage" in text_flags)
        )
        has_under_voltage = bool(
            is_under_voltage_now
            or throttling.undervoltage_past
            or (flags & 0x10000)
        )
        has_throttling = bool(
            (flags & 0x60006)
            or ("throttled" in text_flags)
            or ("arm-frequency-capped" in text_flags)
        )

        self._sync_repair_issue(
            f"undervoltage_{entry_id}",
            has_under_voltage,
            IssueSeverity.CRITICAL if is_under_voltage_now else IssueSeverity.WARNING,
            "undervoltage",
            "https://docs.pikvm.org/power/",
        )
        self._sync_repair_issue(
            f"throttling_{entry_id}",
            has_throttling,
            IssueSeverity.WARNING,
            "throttling",
            "https://docs.pikvm.org/",
        )

    async def _async_update_data(self) -> PiKVMDeviceInfo:
        """Fetch data from PiKVM API."""
        try:
            _LOGGER.debug("Fetching PiKVM Info & MSD from %s", self.url)
            data = await self.client.get_info()
            self._async_check_hardware_health(data)
            return data
        except PiKVMAuthenticationError as auth_err:
            _LOGGER.debug(
                "Authentication failed for PiKVM at %s: %s", self.url, auth_err
            )
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
