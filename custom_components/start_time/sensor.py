import logging
from collections import OrderedDict
from logging import LogRecord

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Started tracking time")

DOMAIN = 'start_time'


class LogsHandler(logging.Handler):
    state = None
    attrs = {}
    add_entities = None

    def handle(self, record: LogRecord) -> None:
        if record.msg.startswith("Setup of domain"):
            self.attrs[record.args[0]] = round(record.args[1], 1)

        elif record.msg.startswith("Home Assistant initialized"):
            self.state = round(record.args[0], 1)
            at = sorted(self.attrs.items(), key=lambda t: t[1], reverse=True)
            self.attrs = OrderedDict(at)
            self.update()

    def update(self):
        if self.state and self.add_entities:
            self.add_entities([StartTime(self.state, self.attrs)])


handler = LogsHandler()

logging.getLogger('homeassistant.bootstrap').addHandler(handler)
logging.getLogger('homeassistant.setup').addHandler(handler)


async def async_setup_platform(hass: HomeAssistantType, config, add_entities,
                               discovery_info=None):
    handler.add_entities = add_entities
    handler.update()
    return True


class StartTime(Entity):
    def __init__(self, state: float, attrs: dict):
        self._state = state
        self._attrs = attrs

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
