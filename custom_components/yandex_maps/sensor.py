"""
A platform which give you the time it will take to drive.

For more details about this component, please refer to the documentation at
https://github.com/custom-components/sensor.yandex_maps
"""
import logging
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

__version__ = '0.0.4'

CONF_NAME = 'name'
CONF_START = 'start'
CONF_DESTINATION = 'destination'

ICON = 'mdi:car'

BASE_URL = 'https://yandex.ru/geohelper/api/v1/router?points={}~{}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_START): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):  # pylint: disable=unused-argument
    """Setup sensor platform."""
    name = config['name']
    start = config['start']
    destination = config['destination']

    async_add_entities(
        [YandexMapsSensor(hass, name, start, destination)], True)

class YandexMapsSensor(Entity):
    """YandexMap Sensor class"""
    def __init__(self, hass, name, start, destination):
        self.hass = hass
        self._state = None
        self._name = name
        self._start = start
        self._destination = destination
        self.attr = {}

    async def async_update(self):
        """Update sensor."""
        _LOGGER.debug('%s - Running update', self._name)
        start = None
        if 'device_tracker' in self._start:
            state = self.hass.states.get(self._start)
            if state:
                latitude = state.attributes.get('latitude')
                longitude = state.attributes.get('longitude')
                if latitude and longitude:
                    start = "{},{}".format(str(longitude), str(latitude))
        if start is None:
            start = self._start
        try:
            url = BASE_URL.format(start, self._destination)
            info = requests.get(url).json()
            self._state = info.get('direct', {}).get('time')
            self.attr = {
                'mapurl': info.get('direct', {}).get('mapUrl'),
                'jamsrate': info.get('jamsRate'),
                'jamsmeasure': info.get('jamsMeasure')
            }
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.debug('%s - Could not update - %s', self._name, error)

    @property
    def name(self):
        """Name."""
        return self._name

    @property
    def state(self):
        """State."""
        return self._state

    @property
    def icon(self):
        """Icon."""
        return ICON

    @property
    def unit_of_measurement(self):
        """unit_of_measurement."""
        return 'мин'

    @property
    def device_state_attributes(self):
        """Attributes."""
        return self.attr
