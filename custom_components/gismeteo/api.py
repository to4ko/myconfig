#  Copyright (c) 2019-2024, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
"""
The Gismeteo component.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""

import logging
import math
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from http import HTTPStatus
from typing import Any, Final

import defusedxml.ElementTree as ETree
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
)
from homeassistant.const import ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.helpers.typing import StateType
from homeassistant.util import Throttle
from homeassistant.util import dt as dt_util

from .cache import Cache
from .const import (
    ATTR_FORECAST_GEOMAGNETIC_FIELD,
    ATTR_FORECAST_IS_STORM,
    ATTR_FORECAST_PHENOMENON,
    ATTR_FORECAST_POLLEN_BIRCH,
    ATTR_FORECAST_POLLEN_GRASS,
    ATTR_FORECAST_POLLEN_RAGWEED,
    ATTR_FORECAST_PRECIPITATION_AMOUNT,
    ATTR_FORECAST_PRECIPITATION_INTENSITY,
    ATTR_FORECAST_PRECIPITATION_TYPE,
    ATTR_FORECAST_ROAD_CONDITION,
    ATTR_FORECAST_WATER_TEMPERATURE,
    ATTR_FORECAST_WIND_BEARING_LABEL,
    ATTR_LAT,
    ATTR_LON,
    ATTR_SUNRISE,
    ATTR_SUNSET,
    CONDITION_FOG_CLASSES,
    ENDPOINT_URL,
    PARSED_UPDATE_INTERVAL,
    PARSER_URL_FORMAT,
    PARSER_USER_AGENT,
    PRECIPITATION_AMOUNT,
    ForecastMode,
)

_LOGGER = logging.getLogger(__name__)

MAX_LATITUDE: Final = 90
MAX_LONGITUDE: Final = 180


class InvalidCoordinatesError(Exception):
    """Raised when coordinates are invalid."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__("Your coordinates are invalid.")


class ApiError(Exception):
    """Raised when Gismeteo API request ended in error."""

    def __init__(self, status: Any) -> None:
        """Initialize."""
        super().__init__(status)


class GismeteoForecast(Forecast, total=False):
    """
    Typed weather forecast dict.

    All attributes are in native units.
    """

    precipitation_type: str | None
    precipitation_intensity: str | None
    wind_bearing_label: str | None
    phenomenon: str | None
    pollen_birch: bool | None
    pollen_grass: bool | None
    pollen_ragweed: bool | None
    road_condition: str | None


class _GettingMethod(Enum):
    REGULAR = 0
    AS_BROWSER = 1


class GismeteoApiClient:
    """Gismeteo API implementation."""

    def __init__(  # noqa: PLR0913
        self,
        session: ClientSession,
        location_key: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        params: dict | None = None,
    ) -> None:
        """Initialize."""
        params = params or {}

        self._session = session
        self._cache = Cache(params) if params.get("cache_dir") is not None else None
        self._latitude = latitude
        self._longitude = longitude
        self._show_on_map = params.get(CONF_SHOW_ON_MAP, False)
        self._attributes = {}

        if location_key is not None:
            _LOGGER.debug("Place location ID used")
            self._attributes = {
                ATTR_ID: location_key,
            }
        elif self._valid_coordinates(latitude, longitude):
            _LOGGER.debug("Place coordinates used")

        else:
            raise InvalidCoordinatesError

        self._current = {}
        self._forecast_hourly = []
        self._forecast_daily = []
        self._parsed = {}

    @staticmethod
    def _valid_coordinates(latitude: float, longitude: float) -> bool:
        """Return True if coordinates are valid."""
        try:
            if (
                not isinstance(latitude, int | float)
                or not isinstance(longitude, int | float)
                or abs(latitude) > MAX_LATITUDE
                or abs(longitude) > MAX_LONGITUDE
            ):
                return False
        except TypeError:
            return False
        else:
            return True

    @property
    def attributes(self) -> dict[str, Any] | None:
        """Return an attributes."""
        attrs = self._attributes.copy()  # type: dict[str, Any]
        if self._show_on_map:
            attrs[ATTR_LATITUDE] = self._latitude
            attrs[ATTR_LONGITUDE] = self._longitude
        else:
            attrs[ATTR_LAT] = self._latitude
            attrs[ATTR_LON] = self._longitude

        return attrs

    @property
    def current_data(self) -> dict[str, Any]:
        """Return current weather data."""
        return self._current

    def forecast_data(
        self, pos: int, mode: str = ForecastMode.HOURLY
    ) -> dict[str, Any]:
        """Return forecast data."""
        now = dt_util.now()
        forecast = []
        for data in (
            self._forecast_hourly
            if mode == ForecastMode.HOURLY
            else self._forecast_daily
        ):
            fc_time = data.get(ATTR_FORECAST_TIME)
            if fc_time is None:
                continue  # pragma: no cover

            if fc_time < now:
                forecast = [data]
            else:
                forecast.append(data)

        try:
            return forecast[pos]

        except IndexError:
            return {}

    async def _async_get_data(
        self,
        url: str,
        cache_fname: str | None = None,
        method: _GettingMethod = _GettingMethod.REGULAR,
    ) -> str:
        """Retreive data from Gismeteo API and cache results."""
        _LOGGER.debug("Requesting URL %s", url)

        if self._cache and cache_fname is not None:
            cache_fname += ".xml"
            if self._cache.is_cached(cache_fname):
                _LOGGER.debug("Cached response used")
                return await self._cache.async_read_cache(cache_fname)

        headers = {}
        if method is _GettingMethod.AS_BROWSER:
            headers["User-Agent"] = PARSER_USER_AGENT

        async with self._session.get(url, headers=headers) as resp:
            if resp.status != HTTPStatus.OK:
                msg = f"Invalid response from Gismeteo API: {resp.status}"
                raise ApiError(msg)
            _LOGGER.debug("Data retrieved from %s, status: %s", url, resp.status)
            data = await resp.text()

        if self._cache and cache_fname is not None and data:
            await self._cache.async_save_cache(cache_fname, data)

        return data

    async def async_update_location(self) -> None:
        """Retreive location data from Gismeteo."""
        if self._latitude == 0 and self._longitude == 0:
            return

        url = (
            ENDPOINT_URL + f"/cities/?lat={self._latitude}"
            f"&lng={self._longitude}&count=1&lang=en"
        )
        cache_fname = f"location_{self._latitude}_{self._longitude}"

        response = await self._async_get_data(url, cache_fname)
        try:
            xml = ETree.fromstring(response)
            item = xml.find("item")
            self._attributes[ATTR_ID] = self._get(item, "id", int)
            self._latitude = self._get(item, "lat", float)
            self._longitude = self._get(item, "lng", float)

        except (ETree.ParseError, TypeError, AttributeError) as ex:
            msg = "Can't retrieve location data! Invalid server response."
            raise ApiError(msg) from ex

    async def async_get_forecast(self) -> str:
        """Get the latest forecast data from Gismeteo API."""
        if ATTR_ID not in self.attributes:
            await self.async_update_location()

            if ATTR_ID not in self.attributes:
                return ""

        url = f"{ENDPOINT_URL}/forecast/?city={self.attributes[ATTR_ID]}&lang=en"
        cache_fname = f"forecast_{self.attributes[ATTR_ID]}"

        return await self._async_get_data(url, cache_fname)

    async def async_get_parsed(self) -> dict[str, Any]:
        """Retrieve data from Gismeteo main site."""
        forecast = await self.async_get_forecast()
        location = ETree.fromstring(forecast).find("location")
        location_uri = str(location.get("nowcast_url")).strip("/")[8:]
        tzone = int(location.get("tzone"))
        today = self._get_utime(location.get("cur_time")[:10], tzone)

        data = {}
        url = PARSER_URL_FORMAT.format(location_uri)
        cache_fname = f"forecast_parsed_{self.attributes[ATTR_ID]}"

        response = await self._async_get_data(
            url, cache_fname, method=_GettingMethod.AS_BROWSER
        )

        parser = BeautifulSoup(response, "html.parser")

        try:
            for row in parser.find_all("div", {"class": "widget-row"}):
                if "data-row" not in row.attrs:
                    continue
                metric = row["data-row"]
                for day, row_data in enumerate(
                    row.find_all("div", {"class": "row-item"})
                ):
                    ts = today + timedelta(days=day)
                    data.setdefault(ts, {})
                    data[ts][metric] = next(row_data.stripped_strings, None)

        except AttributeError:  # pragma: no cover
            return {}
        else:
            return data

    @staticmethod
    def _get(var: dict, k: str, func: Callable | None = None) -> StateType:
        res = var.get(k)
        if func is not None:
            try:
                res = func(res)
            except (TypeError, ValueError, ArithmeticError):
                return None
        return res

    def condition(  # noqa: PLR0912
        self, src: dict | None = None, mode: str = ForecastMode.HOURLY
    ) -> str | None:
        """Return the condition summary."""
        src = src or self._current

        cld = src.get(ATTR_FORECAST_CLOUD_COVERAGE)
        if cld is None:
            return None
        if cld == 0:
            if mode == ForecastMode.DAILY or (
                src.get(ATTR_SUNRISE)
                < src.get(ATTR_FORECAST_TIME, dt_util.now())
                < src.get(ATTR_SUNSET)
            ):
                cond = ATTR_CONDITION_SUNNY  # Sunshine
            else:
                cond = ATTR_CONDITION_CLEAR_NIGHT  # Clear night
        elif cld == 1:
            cond = ATTR_CONDITION_PARTLYCLOUDY  # A few clouds
        elif cld == 2:  # noqa: PLR2004
            cond = ATTR_CONDITION_PARTLYCLOUDY  # A some clouds
        else:
            cond = ATTR_CONDITION_CLOUDY  # Many clouds

        pr_type = src.get(ATTR_FORECAST_PRECIPITATION_TYPE)
        pr_int = src.get(ATTR_FORECAST_PRECIPITATION_INTENSITY)
        if src.get(ATTR_FORECAST_IS_STORM):
            cond = ATTR_CONDITION_LIGHTNING  # Lightning/ thunderstorms
            if pr_type != 0:
                cond = (
                    ATTR_CONDITION_LIGHTNING_RAINY  # Lightning/ thunderstorms and rain
                )
        elif pr_type == 1:
            cond = ATTR_CONDITION_RAINY  # Rain
            if pr_int == 3:  # noqa: PLR2004
                cond = ATTR_CONDITION_POURING  # Pouring rain
        elif pr_type == 2:  # noqa: PLR2004
            cond = ATTR_CONDITION_SNOWY  # Snow
        elif pr_type == 3:  # noqa: PLR2004
            cond = ATTR_CONDITION_SNOWY_RAINY  # Snow and Rain
        elif self.wind_speed(src) > 10.8:  # noqa: PLR2004
            if cond == ATTR_CONDITION_CLOUDY:
                cond = ATTR_CONDITION_WINDY_VARIANT  # Wind and clouds
            else:
                cond = ATTR_CONDITION_WINDY  # Wind
        elif (
            cld == 0
            and src.get(ATTR_FORECAST_PHENOMENON) is not None
            and src.get(ATTR_FORECAST_PHENOMENON) in CONDITION_FOG_CLASSES
        ):
            cond = ATTR_CONDITION_FOG  # Fog

        return cond

    def temperature(self, src: dict | None = None) -> float | None:
        """Return the temperature."""
        src = src or self._current
        return src.get(ATTR_FORECAST_NATIVE_TEMP)

    def templow(self, src: dict | None = None) -> float | None:
        """Return the low temperature of the day."""
        src = src or self._current
        return src.get(ATTR_FORECAST_NATIVE_TEMP_LOW)

    def apparent_temperature(self, src: dict | None = None) -> float | None:
        """Return the apparent temperature."""
        temp = self.temperature(src)
        humi = self.humidity(src)
        wind = self.wind_speed(src)
        if None in (temp, humi, wind):
            return None

        e_value = humi * 0.06105 * math.exp((17.27 * temp) / (237.7 + temp))
        feels = temp + 0.348 * e_value - 0.7 * wind - 4.25
        return round(feels, 1)

    def water_temperature(self, src: dict | None = None) -> float | None:
        """Return the temperature of water."""
        src = src or self._current
        return src.get(ATTR_FORECAST_WATER_TEMPERATURE)

    def pressure(self, src: dict | None = None) -> float | None:
        """Return the pressure in mmHg."""
        src = src or self._current
        return src.get(ATTR_FORECAST_NATIVE_PRESSURE)

    def humidity(self, src: dict | None = None) -> float | None:
        """Return the humidity in %."""
        src = src or self._current
        return src.get(ATTR_FORECAST_HUMIDITY)

    def wind_bearing(self, src: dict | None = None) -> float | str | None:
        """Return the wind bearing."""
        src = src or self._current
        bearing = int(src.get(ATTR_FORECAST_WIND_BEARING, 0))
        return (bearing - 1) * 45 if bearing > 0 else None

    def wind_bearing_label(self, src: dict | None = None) -> str | None:
        """Return the wind bearing."""
        src = src or self._current
        bearing = int(src.get(ATTR_FORECAST_WIND_BEARING, 0))
        try:
            return {
                0: None,
                1: "n",
                2: "ne",
                3: "e",
                4: "se",
                5: "s",
                6: "sw",
                7: "w",
                8: "nw",
            }[bearing]
        except KeyError:  # pragma: no cover
            _LOGGER.exception('Unknown wind bearing value "%s"', bearing)
            return None

    def wind_gust_speed(self, src: dict | None = None) -> float | None:
        """Return the wind gust speed in m/s."""
        src = src or self._current
        return src.get(ATTR_FORECAST_NATIVE_WIND_GUST_SPEED)

    def wind_speed(self, src: dict | None = None) -> float | None:
        """Return the wind speed in m/s."""
        src = src or self._current
        return src.get(ATTR_FORECAST_NATIVE_WIND_SPEED)

    def precipitation_type(self, src: dict | None = None) -> str | None:
        """Return the precipitation type."""
        src = src or self._current
        pt = src.get(ATTR_FORECAST_PRECIPITATION_TYPE)
        try:
            return {
                0: "none",
                1: "rain",
                2: "snow",
                3: "snow-rain",
            }[pt]
        except KeyError:  # pragma: no cover
            _LOGGER.exception('Unknown precipitation type value "%s"', pt)
            return None

    def precipitation_amount(self, src: dict | None = None) -> float | None:
        """Return the precipitation amount in mm."""
        src = src or self._current
        return src.get(ATTR_FORECAST_PRECIPITATION_AMOUNT)

    def precipitation_intensity(self, src: dict | None = None) -> str | None:
        """Return the precipitation intensity."""
        src = src or self._current
        pt = src.get(ATTR_FORECAST_PRECIPITATION_INTENSITY)
        try:
            return {
                0: "none",
                1: "small",
                2: "normal",
                3: "heavy",
            }[pt]
        except KeyError:  # pragma: no cover
            _LOGGER.exception('Unknown precipitation type value "%s"', pt)
            return None

    def cloud_coverage(self, src: dict | None = None) -> float | None:
        """Return the cloud coverage amount in percents."""
        src = src or self._current
        cloudiness = src.get(ATTR_FORECAST_CLOUD_COVERAGE)
        return (
            50
            if cloudiness == 101  # noqa: PLR2004
            else int(cloudiness * 100 / 3) if cloudiness is not None else None
        )

    def rain_amount(self, src: dict | None = None) -> float | None:
        """Return the rain amount in mm."""
        src = src or self._current
        return (
            (
                src.get(ATTR_FORECAST_PRECIPITATION_AMOUNT)
                or PRECIPITATION_AMOUNT[src.get(ATTR_FORECAST_PRECIPITATION_INTENSITY)]
            )
            if src.get(ATTR_FORECAST_PRECIPITATION_TYPE) in [1, 3]
            else 0
        )

    def snow_amount(self, src: dict | None = None) -> float | None:
        """Return the snow amount in mm."""
        src = src or self._current
        return (
            (
                src.get(ATTR_FORECAST_PRECIPITATION_AMOUNT)
                or PRECIPITATION_AMOUNT[src.get(ATTR_FORECAST_PRECIPITATION_INTENSITY)]
            )
            if src.get(ATTR_FORECAST_PRECIPITATION_TYPE) in [2, 3]
            else 0
        )

    def is_storm(self, src: dict | None = None) -> bool | None:
        """Return True if storm."""
        src = src or self._current
        return src.get(ATTR_FORECAST_IS_STORM)

    def geomagnetic_field(self, src: dict | None = None) -> int | None:
        """Return geomagnetic field index."""
        src = src or self._current
        return src.get(ATTR_FORECAST_GEOMAGNETIC_FIELD)

    def pollen_birch(self, src: dict | None = None) -> int | None:
        """Return birch pollen value."""
        src = src or self.forecast_data(0, ForecastMode.DAILY)
        return src.get(ATTR_FORECAST_POLLEN_BIRCH)

    def pollen_grass(self, src: dict | None = None) -> int | None:
        """Return grass pollen value."""
        src = src or self.forecast_data(0, ForecastMode.DAILY)
        return src.get(ATTR_FORECAST_POLLEN_GRASS)

    def pollen_ragweed(self, src: dict | None = None) -> int | None:
        """Return grass pollen value."""
        src = src or self.forecast_data(0, ForecastMode.DAILY)
        return src.get(ATTR_FORECAST_POLLEN_RAGWEED)

    def uv_index(self, src: dict | None = None) -> float | None:
        """Return UV index."""
        src = src or self.forecast_data(0, ForecastMode.DAILY)
        return src.get(ATTR_FORECAST_UV_INDEX)

    def road_condition(self, src: dict | None = None) -> str | None:
        """Return road condition."""
        src = src or self.forecast_data(0, ForecastMode.DAILY)
        rc = src.get(ATTR_FORECAST_ROAD_CONDITION)
        if not rc:
            return None
        rcs = {
            "Нет данных": None,
            "Сухая дорога": "dry",
            "Вода": "water",
            "Влажная дорога": "wet",
        }
        try:
            return rcs[rc]
        except KeyError:  # pragma: no cover
            _LOGGER.exception('Unknown road condition value "%s"', rc)
            return None

    def forecast(self, mode: str = ForecastMode.HOURLY) -> list[GismeteoForecast]:
        """Return the forecast array."""
        now = dt_util.now()
        forecast = []
        for i in (
            self._forecast_hourly
            if mode == ForecastMode.HOURLY
            else self._forecast_daily
        ):
            fc_time = i.get(ATTR_FORECAST_TIME)
            if fc_time is None:
                continue  # pragma: no cover

            data = {
                k: v
                for k, v in {
                    ATTR_FORECAST_TIME: fc_time,
                    ATTR_FORECAST_IS_DAYTIME: i.get(ATTR_FORECAST_IS_DAYTIME),
                    ATTR_FORECAST_CONDITION: self.condition(i, mode),
                    ATTR_FORECAST_NATIVE_APPARENT_TEMP: self.apparent_temperature(i),
                    ATTR_FORECAST_NATIVE_TEMP: self.temperature(i),
                    ATTR_FORECAST_NATIVE_PRESSURE: self.pressure(i),
                    ATTR_FORECAST_HUMIDITY: self.humidity(i),
                    ATTR_FORECAST_WIND_BEARING: self.wind_bearing(i),
                    ATTR_FORECAST_WIND_BEARING_LABEL: self.wind_bearing_label(i),
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.wind_speed(i),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: self.wind_speed(i),
                    ATTR_FORECAST_PRECIPITATION_TYPE: self.precipitation_type(i),
                    ATTR_FORECAST_NATIVE_PRECIPITATION: self.precipitation_amount(i),
                    ATTR_FORECAST_PRECIPITATION_INTENSITY: self.precipitation_intensity(
                        i
                    ),
                    ATTR_FORECAST_UV_INDEX: self.uv_index(i),
                    ATTR_FORECAST_ROAD_CONDITION: self.road_condition(i),
                }.items()
                if v is not None
            }

            if (
                mode == ForecastMode.DAILY
                and i.get(ATTR_FORECAST_NATIVE_TEMP_LOW) is not None
            ):
                data[ATTR_FORECAST_NATIVE_TEMP_LOW] = i.get(
                    ATTR_FORECAST_NATIVE_TEMP_LOW
                )

            if fc_time < now:
                forecast = [data]
            else:
                forecast.append(data)

        return forecast

    @staticmethod
    def _get_utime(source: str, tzone: int) -> datetime:
        """
        Get local datetime for given datetime as string.

        :raise ValueError
        """
        local_date = source
        if len(source) <= 10:  # noqa: PLR2004
            local_date += "T00:00:00"
        tz_h, tz_m = divmod(abs(tzone), 60)
        local_date += f"+{tz_h:02}:{tz_m:02}" if tzone >= 0 else f"-{tz_h:02}:{tz_m:02}"
        return dt_util.parse_datetime(local_date, raise_on_error=True)

    @Throttle(PARSED_UPDATE_INTERVAL)
    async def async_update_parsed(self) -> None:
        """Update parsed data."""
        self._parsed = await self.async_get_parsed()

    async def async_update(self) -> bool:
        """
        Get the latest data from Gismeteo.

        :raise ApiError
        """
        response = await self.async_get_forecast()
        try:
            xml = ETree.fromstring(response)
            current = xml.find("location/fact")
            current_v = current.find("values")
            tzone = int(xml.find("location").get("tzone"))
            today = self._get_utime(current.get("valid"), tzone)

            await self.async_update_parsed()

            self._current = {
                ATTR_SUNRISE: datetime.fromtimestamp(
                    self._get(current, "sunrise", int), today.tzinfo
                ),
                ATTR_SUNSET: datetime.fromtimestamp(
                    self._get(current, "sunset", int), today.tzinfo
                ),
                ATTR_FORECAST_CONDITION: self._get(current_v, "descr"),
                ATTR_FORECAST_NATIVE_TEMP: self._get(current_v, "tflt", float),
                ATTR_FORECAST_NATIVE_PRESSURE: self._get(current_v, "p", int),
                ATTR_FORECAST_HUMIDITY: self._get(current_v, "hum", int),
                ATTR_FORECAST_NATIVE_WIND_SPEED: self._get(current_v, "ws", int),
                ATTR_FORECAST_WIND_BEARING: self._get(current_v, "wd", int),
                ATTR_FORECAST_CLOUD_COVERAGE: self._get(current_v, "cl", int),
                ATTR_FORECAST_PRECIPITATION_TYPE: self._get(current_v, "pt", int),
                ATTR_FORECAST_PRECIPITATION_AMOUNT: self._get(
                    current_v, "prflt", float
                ),
                ATTR_FORECAST_PRECIPITATION_INTENSITY: self._get(current_v, "pr", int),
                ATTR_FORECAST_IS_STORM: (self._get(current_v, "ts") == 1),
                ATTR_FORECAST_GEOMAGNETIC_FIELD: self._get(current_v, "grade", int),
                ATTR_FORECAST_PHENOMENON: self._get(current_v, "ph", int),
                ATTR_FORECAST_WATER_TEMPERATURE: self._get(current_v, "water_t", float),
            }

            # Update hourly forecast
            self._forecast_hourly = []
            for day in xml.findall("location/day"):
                sunrise = datetime.fromtimestamp(
                    self._get(day, "sunrise", int), today.tzinfo
                )
                sunset = datetime.fromtimestamp(
                    self._get(day, "sunset", int), today.tzinfo
                )

                for i in day.findall("forecast"):
                    fc_v = i.find("values")
                    tstamp = self._get_utime(i.get("valid"), tzone)
                    tstamp_day = self._get_utime(i.get("valid")[:10], tzone)
                    data = {
                        ATTR_SUNRISE: sunrise,
                        ATTR_SUNSET: sunset,
                        ATTR_FORECAST_TIME: tstamp,
                        ATTR_FORECAST_IS_DAYTIME: sunrise < tstamp < sunset,
                        ATTR_FORECAST_CONDITION: self._get(fc_v, "descr"),
                        ATTR_FORECAST_NATIVE_TEMP: self._get(fc_v, "t", int),
                        ATTR_FORECAST_NATIVE_PRESSURE: self._get(fc_v, "p", int)
                        or None,
                        ATTR_FORECAST_HUMIDITY: self._get(fc_v, "hum", int),
                        ATTR_FORECAST_NATIVE_WIND_SPEED: self._get(fc_v, "ws", int),
                        ATTR_FORECAST_WIND_BEARING: self._get(fc_v, "wd", int),
                        ATTR_FORECAST_CLOUD_COVERAGE: self._get(fc_v, "cl", int),
                        ATTR_FORECAST_PRECIPITATION_TYPE: self._get(fc_v, "pt", int),
                        ATTR_FORECAST_PRECIPITATION_AMOUNT: self._get(
                            fc_v, "prflt", float
                        ),
                        ATTR_FORECAST_PRECIPITATION_INTENSITY: self._get(
                            fc_v, "pr", int
                        ),
                        ATTR_FORECAST_IS_STORM: (fc_v.get("ts") == 1),
                        ATTR_FORECAST_GEOMAGNETIC_FIELD: self._get(fc_v, "grade", int),
                    }

                    parsed = self._parsed.get(tstamp_day)
                    if parsed:
                        data.update(
                            {
                                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self._get(
                                    parsed, "wind-gust", int
                                ),
                                ATTR_FORECAST_POLLEN_BIRCH: self._get(
                                    parsed, "pollen-birch", int
                                ),
                                ATTR_FORECAST_POLLEN_GRASS: self._get(
                                    parsed, "pollen-grass", int
                                ),
                                ATTR_FORECAST_POLLEN_RAGWEED: self._get(
                                    parsed, "pollen-ragweed", int
                                ),
                                ATTR_FORECAST_UV_INDEX: self._get(
                                    parsed, "radiation", int
                                ),
                                ATTR_FORECAST_ROAD_CONDITION: self._get(
                                    parsed, "roadcondition"
                                ),
                            }
                        )

                    self._forecast_hourly.append(data)

            # Update daily forecast
            self._forecast_daily = []
            for day in xml.findall("location/day[@descr]"):
                tstamp = self._get_utime(day.get("date"), tzone)
                data = {
                    ATTR_SUNRISE: sunrise,
                    ATTR_SUNSET: sunset,
                    ATTR_FORECAST_TIME: tstamp,
                    ATTR_FORECAST_CONDITION: self._get(day, "descr"),
                    ATTR_FORECAST_NATIVE_TEMP: self._get(day, "tmax", int),
                    ATTR_FORECAST_NATIVE_TEMP_LOW: self._get(day, "tmin", int),
                    ATTR_FORECAST_NATIVE_PRESSURE: self._get(day, "p", int) or None,
                    ATTR_FORECAST_HUMIDITY: self._get(day, "hum", int),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: self._get(day, "ws", int),
                    ATTR_FORECAST_WIND_BEARING: self._get(day, "wd", int),
                    ATTR_FORECAST_CLOUD_COVERAGE: self._get(day, "cl", int),
                    ATTR_FORECAST_PRECIPITATION_TYPE: self._get(day, "pt", int),
                    ATTR_FORECAST_PRECIPITATION_AMOUNT: self._get(day, "prflt", float),
                    ATTR_FORECAST_PRECIPITATION_INTENSITY: self._get(day, "pr", int),
                    ATTR_FORECAST_IS_STORM: (self._get(day, "ts") == 1),
                    ATTR_FORECAST_GEOMAGNETIC_FIELD: self._get(day, "grademax", int),
                }

                parsed = self._parsed.get(tstamp)
                if parsed:
                    data.update(
                        {
                            ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self._get(
                                parsed, "wind-gust", int
                            ),
                            ATTR_FORECAST_POLLEN_BIRCH: self._get(
                                parsed, "pollen-birch", int
                            ),
                            ATTR_FORECAST_POLLEN_GRASS: self._get(
                                parsed, "pollen-grass", int
                            ),
                            ATTR_FORECAST_POLLEN_RAGWEED: self._get(
                                parsed, "pollen-ragweed", int
                            ),
                            ATTR_FORECAST_UV_INDEX: self._get(parsed, "radiation", int),
                            ATTR_FORECAST_ROAD_CONDITION: self._get(
                                parsed, "roadcondition"
                            ),
                        }
                    )

                self._forecast_daily.append(data)

        except (ETree.ParseError, TypeError, AttributeError) as ex:
            msg = "Can't update weather data! Invalid server response."
            raise ApiError(msg) from ex
        else:
            return True
