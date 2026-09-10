"""The Ban Allowlist integration."""

from __future__ import annotations

import logging
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from typing import List

import voluptuous as vol
from aiohttp.web import Request
from homeassistant.components.http import ban as http_ban
from homeassistant.components.http.ban import (
    KEY_BAN_MANAGER,
    KEY_FAILED_LOGIN_ATTEMPTS,
    IpBanManager,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("ip_addresses"): vol.All(cv.ensure_list, [cv.string]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Ban Allowlist from a config entry."""
    try:
        ban_manager: IpBanManager = hass.http.app[KEY_BAN_MANAGER]
    except KeyError:
        _LOGGER.warning(
            "Can't find ban manager. ban_allowlist requires http.ip_ban_enabled to be True, so disabling."
        )
        return True
    _LOGGER.debug("Ban manager %s", ban_manager)
    allowlist: List[IPv4Network | IPv6Network] = [
        ip_network(ip) for ip in config.get(DOMAIN, {}).get("ip_addresses", [])
    ]
    if len(allowlist) == 0:
        _LOGGER.info("Not setting allowlist, as no IPs set")
    else:
        _LOGGER.info("Setting allowlist with %s", [str(ip) for ip in allowlist])

        def is_allowed(remote_addr: IPv4Address | IPv6Address) -> bool:
            return any(remote_addr in allowed_network for allowed_network in allowlist)

        original_process_wrong_login = http_ban.process_wrong_login

        async def allowlist_process_wrong_login(request: Request) -> None:
            remote = request.remote
            if remote is not None:
                try:
                    remote_addr = ip_address(remote)
                except ValueError:
                    remote_addr = None
                if remote_addr is not None and is_allowed(remote_addr):
                    attempts = request.app.get(KEY_FAILED_LOGIN_ATTEMPTS)
                    if attempts is not None:
                        attempts.pop(remote_addr, None)
                    _LOGGER.info(
                        "Ignoring invalid authentication from %s because it is in the allowlist",
                        remote_addr,
                    )
                    return

            await original_process_wrong_login(request)

        http_ban.process_wrong_login = allowlist_process_wrong_login

        original_async_add_ban = IpBanManager.async_add_ban

        async def allowlist_async_add_ban(
            remote_addr: IPv4Address | IPv6Address,
        ) -> None:
            if is_allowed(remote_addr):
                _LOGGER.info(
                    "Not adding %s to ban list, as it's in the allowlist",
                    remote_addr,
                )
                return

            _LOGGER.info("Banning IP %s", remote_addr)
            await original_async_add_ban(ban_manager, remote_addr)

        ban_manager.async_add_ban = (  # type:ignore[method-assign]
            allowlist_async_add_ban
        )

    return True
