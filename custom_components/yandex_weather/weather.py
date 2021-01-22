"""
Support for the Yandex.Weather with “Weather on your site” rate.
For more details about Yandex.Weather, please refer to the documentation at
https://tech.yandex.com/weather/

"""


import asyncio
import logging
import socket

import aiohttp
import async_timeout

from datetime import timedelta
import voluptuous as vol
import homeassistant.util.dt as dt_util

from homeassistant.const import (
    CONF_NAME, CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, TEMP_CELSIUS, STATE_UNKNOWN)
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME, ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_HUMIDITY, PLATFORM_SCHEMA, WeatherEntity)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle


import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

TIME_STR_FORMAT = '%H:%M %d.%m.%Y'
DEFAULT_NAME = 'Yandex Weather'
ATTRIBUTION = 'Data provided by Yandex.Weather'

ATTR_FEELS_LIKE = 'feels_like'
ATTR_WEATHER_ICON = 'weather_icon'
ATTR_PRESSURE_MM = 'pressure_mm'
ATTR_OBS_TIME = 'observation_time'
ATTR_WEATHER_CON = 'weather_condition'
ATTR_PRECIPITATION_PROB = 'precipitation_probability'
ATTR_WIND_SPEED_MS = 'wind_speed_ms'

CONDITION_CLASSES = {
    'sunny': ['clear'],
    'partlycloudy': ['partly-cloudy'],
    'cloudy': ['cloudy', 'overcast'],
    'pouring': ['heavy-rain', 'continuous-heavy-rain', 'showers', 'hail'],
    'rainy': ['drizzle', 'light-rain', 'rain', 'moderate-rain'],
    'lightning-rainy': ['thunderstorm', 'thunderstorm-with-rain', 'thunderstorm-with-hail'],
    'snowy-rainy': ['wet-snow'],
    'snowy': ['light-snow', 'snow', 'snow-showers'],
}

DESCRIPTION_DIC = {
    'clear': 'Ясно',
    'partly-cloudy': 'Малооблачно',
    'cloudy': 'Облачно с прояснениями',
    'overcast': 'Пасмурно',
    'heavy-rain': 'Сильный дождь',
    'continuous-heavy-rain': 'Длительный сильный дождь',
    'showers': 'Ливень',
    'hail': 'Град',
    'drizzle': 'Морось',
    'light-rain': 'Небольшой дождь',
    'rain': 'Дождь',
    'moderate-rain': 'Умеренно сильный дождь',
    'thunderstorm': 'Гроза',
    'thunderstorm-with-rain': 'Дождь с грозой',
    'thunderstorm-with-hail': 'Гроза с градом',
    'wet-snow': 'Дождь со снегом',
    'snow': 'Снег',
    'snow-showers': 'Снегопад',
    'light-snow': 'Небольшой снег', 
}

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({    
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
})

async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None):

    """Set up the Yandex.Weather weather platform."""
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    session = async_get_clientsession(hass)
    loop = hass.loop    

    async_add_entities([YandexWeather(name, longitude, latitude, api_key, loop, session)], True)

class YandexWeather (WeatherEntity):
    """Representation of a weather entity."""
    def __init__(self, name: str, longitude: str, latitude: str, api_key: str, loop, session):
        self._name = name
        self._longitude = longitude
        self._latitude = latitude
        self._api_key = api_key
        self._hloop = loop
        self._hsession = session
        self._weather_data = YaWeather(self._latitude, self._longitude, self._api_key, self._hloop, session=self._hsession)
    
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest weather information."""
        await self._weather_data.get_weather()
    
    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature(self) -> int:
        """Return the temperature."""
        if self._weather_data.current is not None:
            return self._weather_data.current.get('temp')
        return None
    
    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS
    
    @property
    def humidity(self) -> int:
        """Return the humidity."""
        if self._weather_data.current is not None:
            return self._weather_data.current.get('humidity')
        return None
    
    @property
    def wind_speed(self) -> float:
        """Return the wind speed."""
        if self._weather_data.current is not None:
            # Convert from m/s to km/h
            return round(self._weather_data.current.get('wind_speed') * 18 / 5)
        return None
    
    @property
    def wind_bearing(self) -> str:
        """Return the wind speed."""
        if self._weather_data.current is not None:
            # The current wind bearing
            return self._weather_data.current.get('wind_dir')
        return None
    
    @property
    def pressure(self) -> int:
        """Return the pressure."""
        if self._weather_data.current is not None:
            return self._weather_data.current.get('pressure_pa')
        return None    
    
    @property
    def condition(self) -> str:
        if self._weather_data.current is not None:
            return next((
            k for k, v in CONDITION_CLASSES.items()
            if self._weather_data.current.get('condition') in v), None)
        return STATE_UNKNOWN

    @property
    def condition_icon(self) -> int:
        """Return the pressure."""
        if self._weather_data.current is not None:
            return self._weather_data.current.get('icon')
        return None 

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._weather_data.forecast is not None:
            fcdata_out = []
            fc_array = self._weather_data.forecast.get('parts', [])
            for data_in in fc_array:
                data_out = {}
                if (list(fc_array).index(data_in) == 0):
                    data_out[ATTR_FORECAST_TIME] = dt_util.utcnow()+timedelta(minutes=350)
                if (list(fc_array).index(data_in) == 1):
                    data_out[ATTR_FORECAST_TIME] = dt_util.utcnow()+timedelta(minutes=700)
                data_out[ATTR_FORECAST_TEMP] = data_in.get('temp_max')
                data_out[ATTR_FORECAST_TEMP_LOW] = data_in.get('temp_min')
                data_out[ATTR_FORECAST_CONDITION] = next((
                    k for k, v in CONDITION_CLASSES.items()
                    if data_in.get('condition') in v), None)
                data_out[ATTR_PRESSURE_MM] = data_in.get('pressure_mm')
                data_out[ATTR_WEATHER_ICON] = data_in.get('icon')
                data_out[ATTR_FEELS_LIKE] = data_in.get('feels_like')
                data_out[ATTR_FORECAST_WIND_SPEED] = round(data_in.get('wind_speed') * 18 / 5) if 'wind_speed' in data_in else None
                data_out[ATTR_FORECAST_WIND_BEARING] = data_in.get('wind_dir')
                data_out[ATTR_FORECAST_PRECIPITATION] = data_in.get('prec_mm')
                data_out[ATTR_PRECIPITATION_PROB] = data_in.get('prec_prob')
                data_out[ATTR_WEATHER_CON] = DESCRIPTION_DIC[data_in.get('condition')]
                data_out[ATTR_WEATHER_PRESSURE] = data_in.get('pressure_pa')
                data_out[ATTR_WEATHER_HUMIDITY] = data_in.get('humidity')
                data_out[ATTR_WIND_SPEED_MS] = data_in.get('wind_speed')
                data_out['part_of_day'] = data_in.get('part_name')
                fcdata_out.append(data_out)

            return fcdata_out
    
    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION
    
    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self._weather_data.current is not None:
            data = dict()
            data[ATTR_FEELS_LIKE] = self._weather_data.current.get('feels_like')
            data[ATTR_PRESSURE_MM] = self._weather_data.current.get('pressure_mm')
            data[ATTR_WIND_SPEED_MS] = self._weather_data.current.get('wind_speed')
            data[ATTR_WEATHER_ICON] = self._weather_data.current.get('icon')
            data[ATTR_OBS_TIME] = dt_util.as_local(dt_util.utc_from_timestamp(self._weather_data.current.get('obs_time'))).strftime(TIME_STR_FORMAT)
            data[ATTR_WEATHER_CON] = DESCRIPTION_DIC[self._weather_data.current.get('condition')]
            return data
        return None 


class YaWeather(object):
    """A class for returning Yandex Weather data."""

    def __init__(self, lat: str, lon: str, api_key, loop, session='none'):
        """Initialize the class."""
        self._api = api_key
        self._lat = lat
        self._lon = lon
        self._loop = loop
        self._session = session
        self._current = None
        self._forecast = None
        

    async def get_weather(self):
        base_url="https://api.weather.yandex.ru/v2/informers?lat=%s&lon=%s" % (self._lat, self._lon)
        headers = {'X-Yandex-API-Key':self._api}       

        try:
            async with async_timeout.timeout(5, loop=self._loop):
                response = await self._session.get(base_url, headers=headers)
            data = await response.json()

            if ('status' not in data):
                self._current = data['fact'] if 'fact' in data else None
                self._forecast = data['forecast'] if 'forecast' in data else None
                _LOGGER.debug(f"Current data:{self._current}")
                _LOGGER.debug(f"Forecast data:{self._forecast}")
            else:
                _LOGGER.error('Error fetching data from Yandex.Weather, %s, %s', data['status'],data['message'])

        except (asyncio.TimeoutError,
                aiohttp.ClientError, socket.gaierror) as error:
            _LOGGER.error('Error fetching data from Yandex.Weather, %s', error)

    @property
    def forecast(self):
        """Return forecast"""
        return self._forecast

    @property
    def current(self):
        """Return curent condition"""
        return self._current
