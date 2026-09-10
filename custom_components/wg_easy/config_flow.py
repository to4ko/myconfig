from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    WGEasyApiError,
    WGEasyAuthError,
    WGEasyNotDetectedError,
    WGEasyV14Client,
    WGEasyV15Client,
    async_probe_wg_easy_version,
)
from .const import (
    API_VERSION_AUTO,
    API_VERSION_V14,
    API_VERSIONS,
    CONF_API_VERSION,
    CONF_RESOLVED_API_VERSION,
    CONF_VERIFY_SSL,
    DEFAULT_ONLINE_TIMEOUT_SECONDS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WGEasyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._url: str | None = None
        self._requested_version: str = API_VERSION_AUTO
        self._effective_version: str | None = None
        self._verify_ssl: bool = DEFAULT_VERIFY_SSL

    async def _async_probe(self, url: str, verify_ssl: bool) -> tuple[str | None, dict[str, str]]:
        """Unauthenticated reachability + version probe (no credentials yet).

        Distinguishes "couldn't reach it at all" from "reached it, but it
        doesn't look like wg-easy" so the form can show a more specific,
        human error instead of a generic "cannot connect" for both.
        """
        session = async_get_clientsession(self.hass)
        try:
            detected = await async_probe_wg_easy_version(session, url, verify_ssl)
        except WGEasyNotDetectedError as err:
            _LOGGER.debug("WG Easy probe: %s does not look like wg-easy: %s", url, err)
            return None, {"base": "not_wg_easy"}
        except WGEasyApiError as err:
            _LOGGER.debug("WG Easy probe failed for %s: %s", url, err)
            return None, {"base": "cannot_connect"}
        return detected, {}

    async def _async_check_credentials(
        self, token: str | None, password: str | None
    ) -> dict[str, str]:
        """Verify the single relevant credential actually authenticates.

        Run for both the initial setup and every reconfigure, before the
        entry is created/updated - so a wrong token/password never gets
        silently saved. Distinguishes "wrong credentials" from "couldn't
        reach the server" so the error shown makes sense either way.
        """
        session = async_get_clientsession(self.hass)
        client = (
            WGEasyV14Client(session, self._url, password, self._verify_ssl)
            if self._effective_version == API_VERSION_V14
            else WGEasyV15Client(session, self._url, token, self._verify_ssl)
        )
        try:
            await client.async_fetch_raw()
        except WGEasyAuthError as err:
            _LOGGER.debug("WG Easy credential check: rejected: %s", err)
            return {"base": "invalid_auth"}
        except WGEasyApiError as err:
            _LOGGER.debug("WG Easy credential check failed: %s", err)
            return {"base": "cannot_connect"}
        return {}

    def _build_entry_data(self, token: str | None, password: str | None) -> dict:
        return {
            CONF_URL: self._url,
            CONF_API_VERSION: self._requested_version,
            CONF_RESOLVED_API_VERSION: self._effective_version,
            CONF_VERIFY_SSL: self._verify_ssl,
            # Always set both keys explicitly (clearing the unused one) so a
            # reconfigure that switches version doesn't leave a stale
            # leftover credential behind in entry.data.
            CONF_TOKEN: token,
            CONF_PASSWORD: password,
        }

    # --- Step 1: address + version + SSL verification --------------------

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            requested_version = user_input.get(CONF_API_VERSION, API_VERSION_AUTO)
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            detected, errors = await self._async_probe(url, verify_ssl)
            if not errors:
                self._url = url
                self._requested_version = requested_version
                self._verify_ssl = verify_ssl
                self._effective_version = (
                    detected if requested_version == API_VERSION_AUTO else requested_version
                )
                return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_address_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            requested_version = user_input.get(CONF_API_VERSION, API_VERSION_AUTO)
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_mismatch(reason="wrong_account")

            detected, errors = await self._async_probe(url, verify_ssl)
            if not errors:
                self._url = url
                self._requested_version = requested_version
                self._verify_ssl = verify_ssl
                self._effective_version = (
                    detected if requested_version == API_VERSION_AUTO else requested_version
                )
                return await self.async_step_reconfigure_credentials()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_address_schema(entry.data),
            errors=errors,
        )

    # --- Step 2: only the one relevant credential ----------------------

    async def async_step_credentials(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input.get(CONF_TOKEN) or None
            password = user_input.get(CONF_PASSWORD) or None

            errors = await self._async_check_credentials(token, password)
            if not errors:
                return self.async_create_entry(
                    title="WG Easy", data=self._build_entry_data(token, password)
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=self._build_credentials_schema(),
            errors=errors,
            description_placeholders={"api_version": self._effective_version or "?"},
        )

    async def async_step_reconfigure_credentials(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input.get(CONF_TOKEN) or None
            password = user_input.get(CONF_PASSWORD) or None

            errors = await self._async_check_credentials(token, password)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=self._url,
                    data_updates=self._build_entry_data(token, password),
                )

        return self.async_show_form(
            step_id="reconfigure_credentials",
            data_schema=self._build_credentials_schema(entry.data),
            errors=errors,
            description_placeholders={"api_version": self._effective_version or "?"},
        )

    # --- Schemas ---------------------------------------------------------

    def _build_address_schema(self, data=None):
        data = data or {}
        return vol.Schema(
            {
                vol.Required(CONF_URL, default=data.get(CONF_URL, "")): str,
                vol.Required(
                    CONF_API_VERSION,
                    default=data.get(CONF_API_VERSION, API_VERSION_AUTO),
                ): vol.In(API_VERSIONS),
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
            }
        )

    def _build_credentials_schema(self, data=None):
        data = data or {}
        if self._effective_version == API_VERSION_V14:
            return vol.Schema(
                {vol.Optional(CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")): str}
            )
        return vol.Schema(
            {vol.Required(CONF_TOKEN, default=data.get(CONF_TOKEN, "")): str}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WGEasyOptionsFlow(config_entry)


class WGEasyOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    "poll_interval",
                    default=self._config_entry.options.get(
                        "poll_interval", DEFAULT_POLL_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                vol.Required(
                    "online_timeout_seconds",
                    default=self._config_entry.options.get(
                        "online_timeout_seconds", DEFAULT_ONLINE_TIMEOUT_SECONDS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
