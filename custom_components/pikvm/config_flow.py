"""Config flow for PiKVM integration."""

from __future__ import annotations

import binascii
import logging
from collections.abc import Mapping
from ipaddress import IPv6Address
from typing import Any

import homeassistant.helpers.config_validation as cv
import pyotp
import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from pikvm_aio import parse_host_port

try:
    from homeassistant.helpers.service_info.zeroconf import (  # type: ignore[import-not-found,unused-ignore]
        ZeroconfServiceInfo,
    )
except ImportError:  # pragma: no cover
    from homeassistant.components.zeroconf import (  # type: ignore[attr-defined,no-redef,unused-ignore]
        ZeroconfServiceInfo,
    )

from .cert_handler import PiKVMResponse, fetch_serialized_cert, is_pikvm_device
from .const import (
    CONF_CERTIFICATE,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_SERIAL,
    CONF_TOTP,
    CONF_USERNAME,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    MANUFACTURER,
)
from .options_flow import PiKVMOptionsFlowHandler
from .utils import (
    create_data_schema,
    find_existing_entry,
    normalize_serial,
    update_existing_entry,
)

_LOGGER = logging.getLogger(__name__)


def _validate_totp(totp_secret: str) -> tuple[str, str | None]:
    """Validate a base32 TOTP secret and return (current_code, error_key)."""
    if not totp_secret:
        return "", None
    try:
        return pyotp.TOTP(totp_secret).now(), None
    except (binascii.Error, ValueError):
        _LOGGER.debug("Invalid base32 string for TOTP secret")
        return "", "invalid_totp"


async def _async_validate_connection(
    hass: HomeAssistant | None,
    host: str,
    username: str,
    password: str,
    totp_secret: str,
    existing_cert: str | None = None,
) -> tuple[PiKVMResponse | None, str, str | None]:
    """Validate TOTP, fetch/reuse certificate, and verify PiKVM device connection.

    Returns (response, serialized_cert, error_key).
    """
    totp_code, totp_err = _validate_totp(totp_secret)
    if totp_err:
        return None, "", totp_err

    serialized_cert = existing_cert
    if serialized_cert is None:
        serialized_cert = await fetch_serialized_cert(hass, host)
        if not serialized_cert:
            return None, "", "cannot_fetch_cert"

    response = await is_pikvm_device(
        hass, host, username, password + totp_code, serialized_cert
    )
    if response.error:
        return None, serialized_cert, response.error
    if not response.success:
        return None, serialized_cert, "cannot_connect"

    return response, serialized_cert, None


async def perform_device_setup(
    flow_handler: PiKVMConfigFlow,
    user_input: dict[str, Any],
) -> tuple[config_entries.ConfigFlowResult | None, dict[str, str] | None]:
    """Handle initial configuration setup for the configuration."""
    errors: dict[str, str] = {}
    host = user_input[CONF_HOST]
    username = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]
    totp_secret = str(user_input.get(CONF_TOTP, "")).strip()

    try:
        response, serialized_cert, err = await _async_validate_connection(
            flow_handler.hass, host, username, password, totp_secret
        )
        if err or response is None:
            errors["base"] = err or "cannot_connect"
            return None, errors

        user_input[CONF_CERTIFICATE] = serialized_cert
        norm_serial = (
            normalize_serial(response.serial)
            or (str(response.serial).strip().lower() if response.serial else None)
        )

        existing_entry = find_existing_entry(flow_handler, norm_serial)
        if existing_entry:
            update_existing_entry(
                flow_handler.hass,
                existing_entry,
                {
                    CONF_HOST: host,
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CONF_TOTP: totp_secret,
                },
            )
            return flow_handler.async_abort(reason="already_configured"), None

        device_name = response.name
        if not device_name or device_name == "localhost.localdomain":
            device_name = MANUFACTURER

        user_input[CONF_TOTP] = totp_secret
        user_input[CONF_MODEL] = (response.model or MANUFACTURER).lower()
        user_input[CONF_SERIAL] = norm_serial
        await flow_handler.async_set_unique_id(norm_serial)

        return (
            flow_handler.async_create_entry(title=device_name, data=user_input),
            None,
        )
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Unexpected error during device setup: %s", e)
        errors["base"] = "unknown_error"
        return None, errors


def _extract_clean_host(raw_host: str) -> str:
    """Safely extract clean host without port or scheme."""
    try:
        return parse_host_port(raw_host)[0]
    except Exception:  # noqa: BLE001
        return raw_host


def _is_entry_host_in_advertised_ips(
    entry: config_entries.ConfigEntry | None, advertised_ipv4s: set[str]
) -> bool:
    """Return True if entry's configured host is already among the device's advertised IPv4s."""
    if entry is None or len(advertised_ipv4s) <= 1:
        return False
    clean_existing = _extract_clean_host(str(entry.data.get(CONF_HOST, "")).strip())
    return bool(clean_existing and clean_existing in advertised_ipv4s)


class PiKVMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PiKVM."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the PiKVMConfigFlow."""
        self.context = {}
        self.handler = DOMAIN
        self._errors: dict[str, str] = {}
        self._discovery_info: dict[str, str] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle the ZeroConf discovery step."""
        raw_serial = discovery_info.properties.get(CONF_SERIAL)
        if isinstance(raw_serial, bytes):
            raw_serial = raw_serial.decode("utf-8", errors="ignore")
        serial = normalize_serial(str(raw_serial) if raw_serial is not None else None)
        ip_addr = getattr(discovery_info, "ip_address", None)
        host = str(discovery_info.host).strip() if discovery_info.host else None

        if not serial or not host or host.lower() == "none" or ip_addr is None:
            return self.async_abort(reason="missing_serial_or_host")

        if ":" in host or isinstance(ip_addr, IPv6Address):
            return self.async_abort(reason="ipv6_address")

        raw_ips = getattr(discovery_info, "ip_addresses", None) or ()
        advertised_ipv4s: set[str] = {
            str(ip).strip()
            for ip in (host, *raw_ips)
            if not isinstance(ip, IPv6Address) and ":" not in str(ip)
        }

        existing_entry = find_existing_entry(self, serial)
        keep_existing_host = _is_entry_host_in_advertised_ips(
            existing_entry, advertised_ipv4s
        )
        updates: dict[str, Any] | None = (
            None if keep_existing_host else {CONF_HOST: host}
        )

        await self.async_set_unique_id(serial)
        try:
            self._abort_if_unique_id_configured(updates=updates)
        except data_entry_flow.AbortFlow as err:
            return self.async_abort(reason=err.reason)

        if existing_entry:
            fallback_updates: dict[str, Any] = {CONF_SERIAL: serial}
            if not keep_existing_host:
                fallback_updates[CONF_HOST] = host
            update_existing_entry(self.hass, existing_entry, fallback_updates)
            return self.async_abort(reason="already_configured")

        self._discovery_info = {
            CONF_HOST: host,
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_TOTP: "",
            CONF_SERIAL: serial,
        }
        return await self._show_zeroconf_menu()

    async def _show_zeroconf_menu(self) -> config_entries.ConfigFlowResult:
        """Show menu for ZeroConf discovered device."""
        return self.async_show_menu(
            step_id="zeroconf_confirm", menu_options=["add_device", "ignore"]
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle user selecting to add the discovered ZeroConf device."""
        return await self.async_step_zeroconf_confirm("add_device")

    async def async_step_ignore(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle user selecting to ignore the discovered ZeroConf device."""
        return await self.async_step_zeroconf_confirm("ignore")

    async def async_step_zeroconf_confirm(
        self, user_input: str | dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle confirmation to add or ignore the ZeroConf device."""
        if user_input == "ignore" or (
            isinstance(user_input, dict) and user_input.get("next_step_id") == "ignore"
        ):
            return self.async_abort(reason="ignored")

        entry, errors = await perform_device_setup(self, self._discovery_info)
        if entry:
            return entry

        self._errors = errors or {}
        return await self.async_step_user(user_input=self._discovery_info)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = self._errors
        self._errors = {}

        if user_input is not None:
            entry, setup_errors = await perform_device_setup(self, user_input)
            if setup_errors:
                errors.update(setup_errors)
            if entry:
                return entry

        if user_input is None:
            user_input = self._discovery_info or {
                CONF_HOST: "",
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: DEFAULT_PASSWORD,
                CONF_TOTP: "",
            }
            if self._discovery_info:
                user_input[CONF_PASSWORD] = ""

        return self.async_show_form(
            step_id="user",
            data_schema=create_data_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle initiation of re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication credentials update."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None and reauth_entry is not None:
            host = reauth_entry.data[CONF_HOST]
            username = user_input.get(
                CONF_USERNAME, reauth_entry.data.get(CONF_USERNAME, DEFAULT_USERNAME)
            )
            password = user_input.get(
                CONF_PASSWORD, reauth_entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            )
            totp_secret = user_input.get(CONF_TOTP, "").strip()
            cert = reauth_entry.data.get(CONF_CERTIFICATE, "")

            response, _, err = await _async_validate_connection(
                self.hass, host, username, password, totp_secret, existing_cert=cert
            )
            if err or response is None:
                errors["base"] = (
                    err
                    if err in ("Exception_HTTP403", "invalid_totp")
                    else "cannot_connect"
                )
            else:
                norm_serial = normalize_serial(response.serial) or response.serial
                expected_serial = normalize_serial(
                    reauth_entry.unique_id or reauth_entry.data.get(CONF_SERIAL)
                )
                if norm_serial and expected_serial and norm_serial != expected_serial:
                    return self.async_abort(reason="unique_id_mismatched")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TOTP: totp_secret,
                    },
                )

        default_username = DEFAULT_USERNAME
        default_password = DEFAULT_PASSWORD
        default_totp = ""
        clean_host = ""
        if reauth_entry is not None:
            default_username = reauth_entry.data.get(CONF_USERNAME, DEFAULT_USERNAME)
            default_password = reauth_entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            default_totp = reauth_entry.data.get(CONF_TOTP, "")
            clean_host = _extract_clean_host(reauth_entry.data.get(CONF_HOST, ""))

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=default_username): str,
                    vol.Required(CONF_PASSWORD, default=default_password): str,
                    vol.Optional(CONF_TOTP, default=default_totp): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": clean_host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_reconfigure_confirm(user_input=user_input)

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of host, port, username, password, and totp."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None and reconfigure_entry is not None:
            host = user_input[CONF_HOST].rstrip("/")
            if (port := user_input.get(CONF_PORT)) and f":{port}" not in host:
                host = f"{host}:{port}"

            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            totp_secret = user_input.get(CONF_TOTP, "").strip()

            response, serialized_cert, err = await _async_validate_connection(
                self.hass, host, username, password, totp_secret
            )
            if err or response is None:
                errors["base"] = (
                    err
                    if err in ("cannot_fetch_cert", "Exception_HTTP403", "invalid_totp")
                    else "cannot_connect"
                )
            else:
                await self.async_set_unique_id(
                    normalize_serial(response.serial) or response.serial
                )
                self._abort_if_unique_id_mismatch(reason="unique_id_mismatched")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        **reconfigure_entry.data,
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TOTP: totp_secret,
                        CONF_CERTIFICATE: serialized_cert,
                        CONF_MODEL: (
                            response.model.lower()
                            if response.model
                            else reconfigure_entry.data.get(CONF_MODEL)
                        ),
                    },
                )

        default_host = ""
        default_username = DEFAULT_USERNAME
        default_password = DEFAULT_PASSWORD
        default_totp = ""
        clean_host = ""
        if reconfigure_entry is not None:
            default_host = reconfigure_entry.data.get(CONF_HOST, "")
            default_username = reconfigure_entry.data.get(
                CONF_USERNAME, DEFAULT_USERNAME
            )
            default_password = reconfigure_entry.data.get(
                CONF_PASSWORD, DEFAULT_PASSWORD
            )
            default_totp = reconfigure_entry.data.get(CONF_TOTP, "")
            clean_host = _extract_clean_host(default_host)

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Optional(CONF_PORT): cv.port,
                    vol.Required(CONF_USERNAME, default=default_username): str,
                    vol.Required(CONF_PASSWORD, default=default_password): str,
                    vol.Optional(CONF_TOTP, default=default_totp): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": clean_host},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PiKVMOptionsFlowHandler()
