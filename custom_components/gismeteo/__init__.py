#
#  Copyright (c) 2019, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
#
"""
The Gismeteo component.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""

import logging
import time
import xml.etree.cElementTree as etree
from datetime import datetime
from urllib.request import urlopen

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_BEARING,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import Throttle, dt as dt_util

from .cache import Cache
from .const import (
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_PRESSURE,
    MIN_TIME_BETWEEN_UPDATES,
    CONDITION_FOG_CLASSES,
    ATTR_SUNRISE,
    ATTR_WEATHER_CLOUDINESS,
    ATTR_SUNSET,
    ATTR_WEATHER_PRECIPITATION_INTENSITY,
    ATTR_WEATHER_PRECIPITATION_TYPE,
    ATTR_WEATHER_STORM,
    ATTR_WEATHER_PHENOMENON,
    ATTR_FORECAST_PRECIPITATION_TYPE,
    ATTR_WEATHER_CONDITION,
    ATTR_WEATHER_PRECIPITATION_AMOUNT,
    ATTR_WEATHER_GEOMAGNETIC_FIELD,
    ATTR_FORECAST_CLOUDINESS,
    ATTR_FORECAST_PRECIPITATION_AMOUNT,
    ATTR_FORECAST_PRECIPITATION_INTENSITY,
    ATTR_FORECAST_STORM,
    ATTR_FORECAST_GEOMAGNETIC_FIELD,
    FORECAST_MODE_HOURLY,
    FORECAST_MODE_DAILY,
    BASE_URL,
    MMHG2HPA,
    MS2KMH,
    VERSION,
    ISSUE_URL,
    DOMAIN,
)

try:
    etree.fromstring('<?xml version="1.0"?><foo><bar/></foo>')
except TypeError:
    # pylint: disable=ungrouped-imports
    import xml.etree.ElementTree as etree  # type: ignore

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup(hass, config):
    """Set up component."""
    # Print startup message
    _LOGGER.info("Version %s", VERSION)
    _LOGGER.info(
        "If you have ANY issues with this, please report them here: %s", ISSUE_URL
    )

    return True


class Gismeteo:
    """Get the latest weather data from Gismeteo."""

    def __init__(
        self, latitude=None, longitude=None, mode=FORECAST_MODE_HOURLY, params=None
    ):
        """Initialize the data object."""
        params = params or {}
        params["domain"] = DOMAIN

        _LOGGER.debug("Place coordinates: %s, %s", latitude, longitude)
        _LOGGER.debug("Forecast mode: %s", mode)

        self._mode = mode
        self._cache = Cache(params) if params.get("cache_dir") is not None else None

        self._city_id = self._get_city_id(latitude, longitude)
        _LOGGER.debug("Nearest city ID: %s", self._city_id)

        self._current = {}
        self._forecast = []
        self._timezone = (
            dt_util.get_time_zone(params.get("timezone"))
            if params.get("timezone") is not None
            else dt_util.DEFAULT_TIME_ZONE
        )

    @property
    def current(self):
        """Return current weather data."""
        return self._current

    def _http_request(self, url, cache_fname=None):
        """Request to API and cache results."""
        if self._cache and cache_fname is not None:
            cache_fname += ".xml"
            if self._cache.is_cached(cache_fname):
                return self._cache.read_cache(cache_fname)

        try:
            req = urlopen(url)
        except OSError:
            return ""

        response = req.read()
        req.close()

        if self._cache and cache_fname is not None and response:
            self._cache.save_cache(cache_fname, response)

        return response

    def _get_city_id(self, lat, lng):
        """Return the nearest city ID."""
        url = (BASE_URL + "/cities/?lat={}&lng={}&count=1&lang=en").format(lat, lng)
        cache_fname = f"city_{lat}_{lng}"

        response = self._http_request(url, cache_fname)
        if not response:
            _LOGGER.error("Can't detect nearest city!")
            return None

        xml = etree.fromstring(response)
        item = xml.find("item")
        return int(item.get("id"))

    @staticmethod
    def _is_day(testing_time, sunrise_time, sunset_time):
        """Return True if sun are shining."""
        return sunrise_time < testing_time < sunset_time

    def condition(self, src=None):
        """Return the current condition."""
        src = src or self._current

        cld = src.get(ATTR_WEATHER_CLOUDINESS)
        if cld is None:
            return None
        if cld == 0:
            if self._mode == FORECAST_MODE_DAILY or self._is_day(
                src.get(ATTR_FORECAST_TIME, time.time()),
                src.get(ATTR_SUNRISE),
                src.get(ATTR_SUNSET),
            ):
                cond = "sunny"  # Sunshine
            else:
                cond = "clear-night"  # Clear night
        elif cld == 1:
            cond = "partlycloudy"  # A few clouds
        elif cld == 2:
            cond = "partlycloudy"  # A some clouds
        else:
            cond = "cloudy"  # Many clouds

        pr_type = src.get(ATTR_WEATHER_PRECIPITATION_TYPE)
        pr_int = src.get(ATTR_WEATHER_PRECIPITATION_INTENSITY)
        if src.get(ATTR_WEATHER_STORM):
            cond = "lightning"  # Lightning/ thunderstorms
            if pr_type != 0:
                cond = "lightning-rainy"  # Lightning/ thunderstorms and rain
        elif pr_type == 1:
            cond = "rainy"  # Rain
            if pr_int == 3:
                cond = "pouring"  # Pouring rain
        elif pr_type == 2:
            cond = "snowy"  # Snow
        elif pr_type == 3:
            cond = "snowy-rainy"  # Snow and Rain
        elif self.wind_speed_ms(src) > 10.8:
            if cond == "cloudy":
                cond = "windy-variant"  # Wind and clouds
            else:
                cond = "windy"  # Wind
        elif (
            cld == 0
            and src.get(ATTR_WEATHER_PHENOMENON) is not None
            and src.get(ATTR_WEATHER_PHENOMENON) in CONDITION_FOG_CLASSES
        ):
            cond = "fog"  # Fog

        return cond

    def temperature(self, src=None):
        """Return the current temperature."""
        src = src or self._current
        temperature = src.get(ATTR_WEATHER_TEMPERATURE)
        return float(temperature) if temperature is not None else STATE_UNKNOWN

    def pressure_mmhg(self, src=None):
        """Return the current pressure in mmHg."""
        src = src or self._current
        pressure = src.get(ATTR_WEATHER_PRESSURE)
        return float(pressure) if pressure is not None else STATE_UNKNOWN

    def pressure_hpa(self, src=None):
        """Return the current pressure in hPa."""
        src = src or self._current
        pressure = src.get(ATTR_WEATHER_PRESSURE)
        return round(pressure * MMHG2HPA, 1) if pressure is not None else STATE_UNKNOWN

    def humidity(self, src=None):
        """Return the name of the sensor."""
        src = src or self._current
        humidity = src.get(ATTR_WEATHER_HUMIDITY)
        return int(humidity) if humidity is not None else STATE_UNKNOWN

    def wind_bearing(self, src=None):
        """Return the current wind bearing."""
        src = src or self._current
        bearing = int(src.get(ATTR_WEATHER_WIND_BEARING, 0))
        return (bearing - 1) * 45 if bearing > 0 else STATE_UNKNOWN

    def wind_speed_kmh(self, src=None):
        """Return the current windspeed in km/h."""
        src = src or self._current
        speed = src.get(ATTR_WEATHER_WIND_SPEED)
        return round(speed * MS2KMH, 1) if speed is not None else STATE_UNKNOWN

    def wind_speed_ms(self, src=None):
        """Return the current windspeed in m/s."""
        src = src or self._current
        speed = src.get(ATTR_WEATHER_WIND_SPEED)
        return float(speed) if speed is not None else STATE_UNKNOWN

    def precipitation_amount(self, src=None):
        """Return the current precipitation amount in mm."""
        src = src or self._current
        precipitation = src.get(ATTR_WEATHER_PRECIPITATION_AMOUNT)
        return precipitation if precipitation is not None else STATE_UNKNOWN

    def forecast(self, src=None):
        """Return the forecast array."""
        src = src or self._forecast
        forecast = []
        now = int(time.time())
        dt_util.set_default_time_zone(self._timezone)
        for i in src:
            fc_time = i.get(ATTR_FORECAST_TIME)
            if fc_time is None:
                continue

            data = {
                ATTR_FORECAST_TIME: dt_util.as_local(
                    datetime.utcfromtimestamp(fc_time)
                ).isoformat(),
                ATTR_FORECAST_CONDITION: self.condition(i),
                ATTR_FORECAST_TEMP: self.temperature(i),
                ATTR_FORECAST_PRESSURE: self.pressure_hpa(i),
                ATTR_FORECAST_HUMIDITY: self.humidity(i),
                ATTR_FORECAST_WIND_SPEED: self.wind_speed_kmh(i),
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing(i),
                ATTR_FORECAST_PRECIPITATION: self.precipitation_amount(i),
            }

            if (
                self._mode == FORECAST_MODE_DAILY
                and i.get(ATTR_FORECAST_TEMP_LOW) is not None
            ):
                data[ATTR_FORECAST_TEMP_LOW] = i.get(ATTR_FORECAST_TEMP_LOW)

            if fc_time < now:
                forecast = [data]
            else:
                forecast.append(data)

        return forecast

    @staticmethod
    def _get_utime(source, tzone):
        local_date = source
        if len(source) <= 10:
            local_date += "T00:00:00"
        tz_h, tz_m = divmod(abs(tzone), 60)
        local_date += f"+{tz_h:02}:{tz_m:02}" if tzone >= 0 else f"-{tz_h:02}:{tz_m:02}"
        return dt_util.as_timestamp(local_date)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Gismeteo."""
        if self._city_id is None:
            return

        url = (BASE_URL + "/forecast/?city={}&lang=en").format(self._city_id)
        cache_fname = f"forecast_{self._city_id}"

        response = self._http_request(url, cache_fname)
        if not response:
            _LOGGER.warning("Can't update weather data!")
            return

        xml = etree.fromstring(response)
        tzone = int(xml.find("location").get("tzone"))
        current = xml.find("location/fact")
        current_v = current.find("values")

        pr_amount = current_v.get("prflt")
        if pr_amount is not None:
            pr_amount = float(pr_amount)

        self._current = {
            ATTR_SUNRISE: int(current.get("sunrise")),
            ATTR_SUNSET: int(current.get("sunset")),
            ATTR_WEATHER_CONDITION: current_v.get("descr"),
            ATTR_WEATHER_TEMPERATURE: float(current_v.get("tflt")),
            ATTR_WEATHER_PRESSURE: int(current_v.get("p")),
            ATTR_WEATHER_HUMIDITY: int(current_v.get("hum")),
            ATTR_WEATHER_WIND_SPEED: int(current_v.get("ws")),
            ATTR_WEATHER_WIND_BEARING: int(current_v.get("wd")),
            ATTR_WEATHER_CLOUDINESS: int(current_v.get("cl")),
            ATTR_WEATHER_PRECIPITATION_TYPE: int(current_v.get("pt")),
            ATTR_WEATHER_PRECIPITATION_AMOUNT: pr_amount,
            ATTR_WEATHER_PRECIPITATION_INTENSITY: int(current_v.get("pr")),
            ATTR_WEATHER_STORM: (current_v.get("ts") == 1),
            ATTR_WEATHER_GEOMAGNETIC_FIELD: int(current_v.get("grade")),
            ATTR_WEATHER_PHENOMENON: int(current_v.get("ph")),
        }

        self._forecast = []
        if self._mode == FORECAST_MODE_HOURLY:
            for day in xml.findall("location/day"):
                sunrise = int(day.get("sunrise"))
                sunset = int(day.get("sunset"))

                for i in day.findall("forecast"):
                    fc_v = i.find("values")

                    pr_amount = fc_v.get("prflt")
                    if pr_amount is not None:
                        pr_amount = float(pr_amount)

                    data = {
                        ATTR_SUNRISE: sunrise,
                        ATTR_SUNSET: sunset,
                        ATTR_FORECAST_TIME: self._get_utime(i.get("valid"), tzone),
                        ATTR_FORECAST_CONDITION: fc_v.get("descr"),
                        ATTR_FORECAST_TEMP: int(fc_v.get("t")),
                        ATTR_FORECAST_PRESSURE: int(fc_v.get("p")),
                        ATTR_FORECAST_HUMIDITY: int(fc_v.get("hum")),
                        ATTR_FORECAST_WIND_SPEED: int(fc_v.get("ws")),
                        ATTR_FORECAST_WIND_BEARING: int(fc_v.get("wd")),
                        ATTR_FORECAST_CLOUDINESS: int(fc_v.get("cl")),
                        ATTR_FORECAST_PRECIPITATION_TYPE: int(fc_v.get("pt")),
                        ATTR_FORECAST_PRECIPITATION_AMOUNT: pr_amount,
                        ATTR_FORECAST_PRECIPITATION_INTENSITY: int(fc_v.get("pr")),
                        ATTR_FORECAST_STORM: (fc_v.get("ts") == 1),
                        ATTR_FORECAST_GEOMAGNETIC_FIELD: int(fc_v.get("grade")),
                    }

                    self._forecast.append(data)

        else:  # self._mode == FORECAST_MODE_DAILY
            for day in xml.findall("location/day[@descr]"):
                pr_amount = day.get("prflt")
                if pr_amount is not None:
                    pr_amount = float(pr_amount)

                data = {
                    ATTR_SUNRISE: int(day.get("sunrise")),
                    ATTR_SUNSET: int(day.get("sunset")),
                    ATTR_FORECAST_TIME: self._get_utime(day.get("date"), tzone),
                    ATTR_FORECAST_CONDITION: day.get("descr"),
                    ATTR_FORECAST_TEMP: int(day.get("tmax")),
                    ATTR_FORECAST_TEMP_LOW: int(day.get("tmin")),
                    ATTR_FORECAST_PRESSURE: int(day.get("p")),
                    ATTR_FORECAST_HUMIDITY: int(day.get("hum")),
                    ATTR_FORECAST_WIND_SPEED: int(day.get("ws")),
                    ATTR_FORECAST_WIND_BEARING: int(day.get("wd")),
                    ATTR_FORECAST_CLOUDINESS: int(day.get("cl")),
                    ATTR_FORECAST_PRECIPITATION_TYPE: int(day.get("pt")),
                    ATTR_FORECAST_PRECIPITATION_AMOUNT: pr_amount,
                    ATTR_FORECAST_PRECIPITATION_INTENSITY: int(day.get("pr")),
                    ATTR_FORECAST_STORM: (day.get("ts") == 1),
                    ATTR_FORECAST_GEOMAGNETIC_FIELD: int(day.get("grademax")),
                }

                self._forecast.append(data)
