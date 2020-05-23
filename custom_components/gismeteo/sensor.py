#
#  Copyright (c) 2019, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
#
"""
The Gismeteo Sensor.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""
import logging

import voluptuous as vol
from homeassistant.components.weather import ATTR_FORECAST_CONDITION, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    TEMP_CELSIUS,
    CONF_API_KEY,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.storage import STORAGE_DIR

from . import Gismeteo
from .const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    MIN_TIME_BETWEEN_UPDATES,
    CONF_CACHE_DIR,
    ATTR_WEATHER_CLOUDINESS,
    ATTR_WEATHER_PRECIPITATION_TYPE,
    ATTR_WEATHER_PRECIPITATION_AMOUNT,
    ATTR_WEATHER_PRECIPITATION_INTENSITY,
    ATTR_WEATHER_STORM,
    ATTR_WEATHER_GEOMAGNETIC_FIELD,
)

_LOGGER = logging.getLogger(__name__)

CONF_FORECAST = "forecast"
CONF_LANGUAGE = "language"

PRECIPITATION_AMOUNT = (0, 2, 6, 16)

SENSOR_TYPES = {
    "weather": ["Condition", None, None],
    "temperature": ["Temperature", TEMP_CELSIUS, None],
    "wind_speed": ["Wind speed", "m/s", "mdi:weather-windy"],
    "wind_bearing": ["Wind bearing", "°", "mdi:weather-windy"],
    "humidity": ["Humidity", "%", None],
    "pressure": ["Pressure", "hPa", None],
    "clouds": ["Cloud coverage", "%", "mdi:weather-partlycloudy"],
    "rain": ["Rain", "mm", "mdi:weather-rainy"],
    "snow": ["Snow", "mm", "mdi:weather-snowy"],
    "storm": ["Storm", None, "mdi:weather-lightning"],
    "geomagnetic": ["Geomagnetic field", "", "mdi:magnet-on"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_FORECAST, default=False): cv.boolean,
        vol.Optional(CONF_CACHE_DIR): cv.string,
        vol.Optional(CONF_LANGUAGE): cv.string,
    }
)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gismeteo weather platform."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return
    latitude = round(hass.config.latitude, 6)
    longitude = round(hass.config.longitude, 6)

    name = config.get(CONF_NAME)
    forecast = config.get(CONF_FORECAST)
    cache_dir = config.get(CONF_CACHE_DIR, hass.config.path(STORAGE_DIR))

    gism = Gismeteo(
        latitude,
        longitude,
        params={
            "timezone": str(hass.config.time_zone),
            "cache_dir": cache_dir,
            "cache_time": MIN_TIME_BETWEEN_UPDATES.total_seconds(),
        },
    )

    dev = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(
            GismeteoSensor(
                name,
                gism,
                variable,
                SENSOR_TYPES[variable][1],
                SENSOR_TYPES[variable][2],
            )
        )

    if forecast:
        SENSOR_TYPES["forecast"] = ["Forecast", None, None]
        dev.append(
            GismeteoSensor(
                name,
                gism,
                "forecast",
                SENSOR_TYPES["forecast"][1],
                SENSOR_TYPES["forecast"][2],
            )
        )

    add_entities(dev, True)


class GismeteoSensor(Entity):
    """Implementation of an Gismeteo sensor."""

    def __init__(self, station_name, weather_data, sensor_type, temp_unit, icon):
        """Initialize the sensor."""
        self.client_name = station_name
        self._name = SENSOR_TYPES[sensor_type][0]
        self._wd = weather_data
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = icon

    def update(self):
        """Get the latest data from Gismeteo and updates the states."""
        self._wd.update()

        if self._wd.current is None:
            return

        data = self._wd.current
        try:
            if self.type == "weather":
                self._state = self._wd.condition()
            elif self.type == "forecast":
                self._state = self._wd.forecast()[0][ATTR_FORECAST_CONDITION]
            elif self.type == "temperature":
                self._state = self._wd.temperature()
            elif self.type == "wind_speed":
                self._state = self._wd.wind_speed_ms()
            elif self.type == "wind_bearing":
                self._state = self._wd.wind_bearing()
            elif self.type == "humidity":
                self._state = self._wd.humidity()
            elif self.type == "pressure":
                self._state = self._wd.pressure_hpa()
            elif self.type == "clouds":
                self._state = int(data.get(ATTR_WEATHER_CLOUDINESS) * 33.33)
            elif self.type == "rain":
                if data.get(ATTR_WEATHER_PRECIPITATION_TYPE) in [1, 3]:
                    self._state = (
                        data.get(ATTR_WEATHER_PRECIPITATION_AMOUNT)
                        or PRECIPITATION_AMOUNT[
                            data.get(ATTR_WEATHER_PRECIPITATION_INTENSITY)
                        ]
                    )
                    self._unit_of_measurement = SENSOR_TYPES["rain"][1]
                else:
                    self._state = "not raining"
                    self._unit_of_measurement = ""
            elif self.type == "snow":
                if data.get(ATTR_WEATHER_PRECIPITATION_TYPE) in [2, 3]:
                    self._state = (
                        data.get(ATTR_WEATHER_PRECIPITATION_AMOUNT)
                        or PRECIPITATION_AMOUNT[
                            data.get(ATTR_WEATHER_PRECIPITATION_INTENSITY)
                        ]
                    )
                    self._unit_of_measurement = SENSOR_TYPES["snow"][1]
                else:
                    self._state = "not snowing"
                    self._unit_of_measurement = ""
            elif self.type == "storm":
                self._state = data.get(ATTR_WEATHER_STORM)
            elif self.type == "geomagnetic":
                self._state = data.get(ATTR_WEATHER_GEOMAGNETIC_FIELD)
        except KeyError:
            self._state = None
            _LOGGER.warning("Condition is currently not available: %s", self.type)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon
