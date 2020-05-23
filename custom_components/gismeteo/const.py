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

from datetime import timedelta

from homeassistant.components.weather import ATTR_FORECAST_CONDITION

# Base component constants
DOMAIN = "gismeteo"
VERSION = "2.0.14"
ISSUE_URL = "https://github.com/Limych/ha-gismeteo/issues"
ATTRIBUTION = "Data provided by Gismeteo"

BASE_URL = "https://services.gismeteo.ru/inform-service/inf_chrome"

MMHG2HPA = 1.333223684
MS2KMH = 3.6

CONF_CACHE_DIR = "cache_dir"

FORECAST_MODE_HOURLY = "hourly"
FORECAST_MODE_DAILY = "daily"

DEFAULT_NAME = "Gismeteo"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONDITION_FOG_CLASSES = [
    11,
    12,
    28,
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    120,
    130,
    131,
    132,
    133,
    134,
    135,
    528,
]

ATTR_SUNRISE = "sunrise"
ATTR_SUNSET = "sunset"

ATTR_WEATHER_CONDITION = ATTR_FORECAST_CONDITION
ATTR_WEATHER_CLOUDINESS = "cloudiness"
ATTR_WEATHER_PRECIPITATION_TYPE = "precipitation_type"
ATTR_WEATHER_PRECIPITATION_AMOUNT = "precipitation_amount"
ATTR_WEATHER_PRECIPITATION_INTENSITY = "precipitation_intensity"
ATTR_WEATHER_STORM = "storm"
ATTR_WEATHER_GEOMAGNETIC_FIELD = "gm_field"
ATTR_WEATHER_PHENOMENON = "phenomenon"

ATTR_FORECAST_HUMIDITY = "humidity"
ATTR_FORECAST_PRESSURE = "pressure"
ATTR_FORECAST_CLOUDINESS = ATTR_WEATHER_CLOUDINESS
ATTR_FORECAST_PRECIPITATION_TYPE = ATTR_WEATHER_PRECIPITATION_TYPE
ATTR_FORECAST_PRECIPITATION_AMOUNT = ATTR_WEATHER_PRECIPITATION_AMOUNT
ATTR_FORECAST_PRECIPITATION_INTENSITY = ATTR_WEATHER_PRECIPITATION_INTENSITY
ATTR_FORECAST_STORM = ATTR_WEATHER_STORM
ATTR_FORECAST_GEOMAGNETIC_FIELD = ATTR_WEATHER_GEOMAGNETIC_FIELD
ATTR_FORECAST_PHENOMENON = ATTR_WEATHER_PHENOMENON
