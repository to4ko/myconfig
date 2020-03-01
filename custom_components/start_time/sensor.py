import logging
from datetime import datetime

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'start_time'


async def async_setup_platform(hass: HomeAssistantType, config, add_entities,
                               discovery_info=None):
    logger = logging.getLogger('homeassistant.bootstrap')
    real_info = logger.info

    def monkey_info(msg: str, *args):
        if msg.startswith("Home Assistant initialized"):
            add_entities([StartTime(args[0])])
        real_info(msg, *args)

    logger.info = monkey_info

    return True


class StartTime(Entity):
    def __init__(self, duration: float):
        self._attrs = {
            'datetime': datetime.now(),
        }
        self._state = round(duration, 1)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self):
        return DOMAIN

    @property
    def name(self):
        return "Start Time"

    @property
    def state(self):
        return self._state

    @property
    def state_attributes(self):
        return self._attrs

    @property
    def unit_of_measurement(self):
        return 'seconds'

    @property
    def icon(self):
        return 'mdi:home-assistant'
