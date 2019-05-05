"""Adguard stats sensors."""

import logging

from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from . import DOMAIN
from . import MONITORED_CONDITIONS

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Adguard Home sensors."""
    
    if not discovery_info:
        return    

    data = hass.data[DOMAIN]

    name = data.get('name')
    sensor_data = data.get('data')    
    conditions = discovery_info
    
    sensors = [AdguardSensor(sensor_data, name, condition)
               for condition in conditions]
    
    sensors.append(AdguardSensor(sensor_data, name,'version'))
    
    async_add_entities(sensors, True)

class AdguardSensor(Entity):
    """Representation of a Adguard sensor."""

    def __init__(self, data, name, condition):
        """Initialize a Adguard sensor."""
        self._data = data
        self._name = name
        self._condition = condition

        variable_info = MONITORED_CONDITIONS[condition]
        self._condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._name, self._condition_name)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement
    
    @property
    def state(self):
        """Return the state of the device."""
        try:
            if self._condition == 'version':
                status = self._data.status
                return status.get('version')

            return getattr(self._data,self._condition)
        except Exception as error:
            _LOGGER.error('Unexpected error from AdGuard, %s', error)
            self._available = False
    
    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Adguard."""
        
        try:
            await self._data.get_update()
            self._available = True
        except Exception as error:
            _LOGGER.error('Unexpected error from AdGuard, %s', error)
            self._available = False


