import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

DOMAIN = 'start_time'


async def async_setup_entry(hass: HomeAssistantType, entry,
                            async_add_entities):
    sensor = hass.data[DOMAIN]
    async_add_entities([sensor])


class StartTime(Entity):
    _state = None
    _attrs = None

    def __init__(self):
        self.add_logger('homeassistant.bootstrap')

    def add_logger(self, name: str):
        logger = logging.getLogger(name)
        real_info = logger.info

        def monkey_info(msg: str, *args):
            if msg.startswith("Home Assistant initialized"):
                self.internal_update(args[0])

            real_info(msg, *args)

        logger.info = monkey_info

    @property
    def should_poll(self):
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
    def extra_state_attributes(self):
        return self._attrs

    @property
    def unit_of_measurement(self):
        return 'seconds'

    @property
    def icon(self):
        return 'mdi:home-assistant'

    def internal_update(self, state):
        setup_time: dict = self.hass.data.get('setup_time')
        if setup_time:
            self._attrs = {
                integration: round(timedelta.total_seconds(), 1)
                for integration, timedelta in sorted(
                    setup_time.items(),
                    key=lambda kv: kv[1].total_seconds(),
                    reverse=True
                )
            }

        self._state = round(state, 1)
        self.schedule_update_ha_state()
