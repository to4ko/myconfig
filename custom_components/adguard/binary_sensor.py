"""Adguard binary sensors."""

import logging

from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASS_SAFETY)

from . import DOMAIN

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS = {    
    'protection_enabled':
        ['Protection','mdi:filter'],
    'querylog_enabled':
        ['Querylog','mdi:file-document-edit'],
    'running':
        ['Runnig','mdi:play-circle-outline']
}

async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Adguard Home binary sensors."""
    
    if not discovery_info:
        return    
    
    data = hass.data[DOMAIN]
    name = data.get('name')
    sensor_data = data.get('data')
    sensors = discovery_info
    
    sensors = [AdguardBinarySensor(sensor_data, name, sensor)
                for sensor in sensors]
    
    async_add_entities(sensors, True)

class AdguardBinarySensor(BinarySensorDevice):
    """Representation of a Adguard binary sensor."""

    def __init__(self, data, name, sensor):
        """Initialize a Adguard sensor."""

        self._data = data
        self._name = name
        self._sensor = sensor
        self._state = None

        variable_info = BINARY_SENSORS[sensor]

        self._sensor_name = variable_info[0]
        self._icon = variable_info[1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._name, self._sensor_name)
    
    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon
    
    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available
    
    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state
        
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Adguard."""
        
        try:
            await self._data.get_update()
            self._available = True

            if self._sensor == 'protection_enabled':
                self._state = bool(self._data.protection_enabled)
                _LOGGER.debug('Protection: %s', self._state)
            if self._sensor == 'querylog_enabled':
                    self._state = bool(self._data.querylog_enabled)
                    _LOGGER.debug('Querylog: %s', self._state)
            if self._sensor == 'running':
                    self._state = bool(self._data.running)
                    _LOGGER.debug('Running: %s', self._state)

        except Exception as error:
            _LOGGER.error('Unexpected error from AdGuard, %s', error)
            self._available = False
