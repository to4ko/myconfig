#
#  Copyright (c) 2019, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
#
"""
The Gismeteo Weather Provider.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""
import logging

import voluptuous as vol
from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (
    TEMP_CELSIUS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_API_KEY,
    CONF_MODE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from . import Gismeteo
from .const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    MIN_TIME_BETWEEN_UPDATES,
    CONF_CACHE_DIR,
    FORECAST_MODE_HOURLY,
    FORECAST_MODE_DAILY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_MODE, default=FORECAST_MODE_HOURLY): vol.In(
            [FORECAST_MODE_HOURLY, FORECAST_MODE_DAILY]
        ),
        vol.Optional(CONF_CACHE_DIR): cv.string,
    }
)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gismeteo weather platform."""
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, round(hass.config.latitude, 6))
    longitude = config.get(CONF_LONGITUDE, round(hass.config.longitude, 6))
    cache_dir = config.get(CONF_CACHE_DIR, hass.config.path(STORAGE_DIR))
    mode = config.get(CONF_MODE)

    gism = Gismeteo(
        latitude,
        longitude,
        mode,
        params={
            "timezone": str(hass.config.time_zone),
            "cache_dir": cache_dir,
            "cache_time": MIN_TIME_BETWEEN_UPDATES.total_seconds(),
        },
    )

    add_entities([GismeteoWeather(name, gism)], True)


class GismeteoWeather(WeatherEntity):
    """Implementation of an Gismeteo sensor."""

    def __init__(self, station_name, weather_data):
        """Initialize the sensor."""
        self._station_name = station_name
        self._wd = weather_data

    def update(self):
        """Get the latest data from Gismeteo and updates the states."""
        self._wd.update()

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._station_name

    @property
    def condition(self):
        """Return the current condition."""
        return self._wd.condition()

    @property
    def temperature(self):
        """Return the current temperature."""
        return self._wd.temperature()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the current pressure."""
        return self._wd.pressure_hpa()

    @property
    def humidity(self):
        """Return the name of the sensor."""
        return self._wd.humidity()

    @property
    def wind_bearing(self):
        """Return the current wind bearing."""
        return self._wd.wind_bearing()

    @property
    def wind_speed(self):
        """Return the current windspeed."""
        return self._wd.wind_speed_kmh()

    @property
    def forecast(self):
        """Return the forecast array."""
        return self._wd.forecast()
