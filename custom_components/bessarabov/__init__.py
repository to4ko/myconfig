"""bessarabov custom component"""

import aiohttp
import logging
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.const import __version__ as localversion
from homeassistant.const import CONF_TOKEN

DOMAIN = "bessarabov"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_TOKEN): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):
    async def _send_data(self, *args, **kwargs) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post('https://ha.bessarabov.com/api/1/version', json={'token': config[DOMAIN][CONF_TOKEN], 'version': localversion}) as resp:
                _LOGGER.info(resp.status)
                _LOGGER.info(await resp.text())

        async_call_later(hass, 3600, _send_data)

    async_call_later(hass, 1, _send_data)

    return True
