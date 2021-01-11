import logging
import time
from datetime import datetime

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

logger = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    add_entities([SlowSensor(config)])


class SlowSensor(Entity):
    _state = None

    def __init__(self, config: dict):
        self.config = config

    @property
    def name(self):
        return self.config.get(CONF_NAME, "Slow Sensor")

    @property
    def state(self):
        return self._state

    @property
    def device_class(self):
        return 'timestamp'

    async def async_update(self):
        sleep = self.config.get('sleep', 5)
        time.sleep(sleep)
        self._state = datetime.now().isoformat(timespec='seconds')
