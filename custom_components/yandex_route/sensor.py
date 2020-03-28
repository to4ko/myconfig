"""
https://gist.github.com/andreypolyak/b2467c7231384ff06ef269b628e5029b
https://github.com/custom-components/sensor.yandex_maps/blob/master/custom_components/yandex_maps/sensor.py
"""
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import HomeAssistantType

from .utils import YandexRouter

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'yandex_route'

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('points'): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    vol.Optional('params', default={}): vol.Schema({}, extra=vol.ALLOW_EXTRA),
})


async def async_setup_platform(hass: HomeAssistantType, config: dict,
                               add_entities, discovery_info=None):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = YandexRouter(hass)

    add_entities([YandexRoute(config, hass.data[DOMAIN])])

    return True


class YandexRoute(Entity):
    def __init__(self, config: dict, router: YandexRouter):
        self._name = config.get(CONF_NAME)
        self._points = config['points']
        self._params = config['params']
        self._delay = config[CONF_SCAN_INTERVAL].total_seconds()

        self._router = router
        self._attrs = None

    async def async_added_to_hass(self) -> None:
        self.hass.async_create_task(self.update())

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return round(self._attrs['duration'] / 60) if self._attrs else None

    @property
    def state_attributes(self):
        return self._attrs

    @property
    def unit_of_measurement(self):
        return 'мин'

    async def update(self):
        _LOGGER.debug(f"Update {self.entity_id}")

        self._attrs = await self._router.build(self._points, self._params)

        self.async_schedule_update_ha_state()

        delay = self._delay if self._attrs else 30
        async_call_later(self.hass, delay, self.update())
