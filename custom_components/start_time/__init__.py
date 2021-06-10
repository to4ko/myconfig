from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.helpers.typing import HomeAssistantType

from .sensor import DOMAIN, StartTime


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    hass.data[DOMAIN] = StartTime()

    if DOMAIN in hass_config:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}
        ))
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, 'sensor'
    ))
    return True
