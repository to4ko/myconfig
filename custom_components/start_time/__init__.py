from homeassistant.helpers import discovery
from homeassistant.helpers.typing import HomeAssistantType

from .sensor import DOMAIN


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    hass.async_create_task(discovery.async_load_platform(
        hass, 'sensor', DOMAIN, None, hass_config))
    return True
