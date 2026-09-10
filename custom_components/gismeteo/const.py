#  Copyright (c) 2019-2024, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
"""
The Gismeteo component.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""

from datetime import timedelta
from enum import StrEnum
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.weather import (
    ATTR_FORECAST_APPARENT_TEMP,
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_GUST_SPEED,
    ATTR_FORECAST_WIND_SPEED,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    Platform,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

# Base component constants
NAME: Final = "Gismeteo"
DOMAIN: Final = "gismeteo"
VERSION: Final = "3.1.0"
ATTRIBUTION: Final = "Data provided by Gismeteo"
ISSUE_URL: Final = "https://github.com/Limych/ha-gismeteo/issues"
#
DOMAIN_YAML: Final = f"{DOMAIN}_yaml"

STARTUP_MESSAGE: Final = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have ANY issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

# Platforms
PLATFORMS: Final = [Platform.SENSOR, Platform.WEATHER]

# Configuration and options
CONF_TIMEZONE: Final = "timezone"
CONF_CACHE_DIR: Final = "cache_dir"
CONF_CACHE_TIME: Final = "cache_time"
CONF_ADD_SENSORS: Final = "add_sensors"
CONF_FORECAST_DAYS: Final = "forecast_days"

# Defaults
DEFAULT_NAME: Final = "Gismeteo"

# Attributes
ATTR_SUNRISE: Final = "sunrise"
ATTR_SUNSET: Final = "sunset"
#
ATTR_FORECAST_WIND_BEARING_LABEL: Final = "wind_bearing_label"
ATTR_FORECAST_PRECIPITATION_TYPE: Final = "precipitation_type"
ATTR_FORECAST_PRECIPITATION_AMOUNT: Final = "precipitation_amount"
ATTR_FORECAST_PRECIPITATION_INTENSITY: Final = "precipitation_intensity"
ATTR_FORECAST_IS_STORM: Final = "is_storm"
ATTR_FORECAST_GEOMAGNETIC_FIELD: Final = "geomagnetic_field"
ATTR_FORECAST_PHENOMENON: Final = "phenomenon"
ATTR_FORECAST_WATER_TEMPERATURE: Final = "water_temperature"
ATTR_FORECAST_POLLEN_BIRCH = "pollen_birch"
ATTR_FORECAST_POLLEN_GRASS = "pollen_grass"
ATTR_FORECAST_POLLEN_RAGWEED = "pollen_ragweed"
ATTR_FORECAST_UV_INDEX = "uv_index"
ATTR_FORECAST_ROAD_CONDITION: Final = "road_condition"
ATTR_FORECAST_RAIN_AMOUNT: Final = "rain_amount"
ATTR_FORECAST_SNOW_AMOUNT: Final = "snow_amount"
#
ATTR_LAT = "lat"
ATTR_LON = "lon"

COORDINATOR: Final = "coordinator"
UNDO_UPDATE_LISTENER: Final = "undo_update_listener"

ENDPOINT_URL: Final = "https://services.gismeteo.ru/inform-service/inf_chrome"
#
PARSER_URL_FORMAT: Final = "https://www.gismeteo.ru/weather-{}/10-days/"
PARSER_USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/128.0.0.0 Safari/537.36"
)

UPDATE_INTERVAL: Final = timedelta(minutes=5)
PARSED_UPDATE_INTERVAL: Final = timedelta(minutes=61)
LOCATION_MAX_CACHE_INTERVAL: Final = timedelta(days=7)
FORECAST_MAX_CACHE_INTERVAL: Final = timedelta(hours=3)

CONDITION_FOG_CLASSES: Final = [
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

PRECIPITATION_AMOUNT: Final = (0, 2, 6, 16)

DEVICE_CLASS_TPL: Final = DOMAIN + "__{}"


class ForecastMode(StrEnum):
    """Forecast modes."""

    HOURLY = "hourly"
    DAILY = "daily"


SENSOR_DESCRIPTIONS: Final = (
    SensorEntityDescription(
        key=ATTR_FORECAST_CONDITION,
        translation_key="condition",
        has_entity_name=True,
        device_class=DEVICE_CLASS_TPL.format("condition"),
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_TEMP,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_APPARENT_TEMP,
        translation_key="apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_HUMIDITY,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_PRESSURE,
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MMHG,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_PRECIPITATION_AMOUNT,
        translation_key="precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_SPEED,
        translation_key="wind_speed",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_BEARING,
        translation_key="wind_bearing",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_BEARING_LABEL,
        translation_key="wind_bearing_label",
        icon="mdi:weather-windy",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_CLOUD_COVERAGE,
        translation_key="cloud_coverage",
        icon="mdi:weather-partly-cloudy",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_RAIN_AMOUNT,
        translation_key="rain_amount",
        icon="mdi:weather-rainy",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_SNOW_AMOUNT,
        translation_key="snow_amount",
        icon="mdi:weather-snowy",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_IS_STORM,
        translation_key="is_storm",
        icon="mdi:weather-lightning",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_GEOMAGNETIC_FIELD,
        translation_key="geomagnetic_field",
        icon="mdi:magnet-on",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WATER_TEMPERATURE,
        translation_key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_UV_INDEX,
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_POLLEN_BIRCH,
        translation_key="pollen_birch",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_POLLEN_GRASS,
        translation_key="pollen_grass",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_POLLEN_RAGWEED,
        translation_key="pollen_ragweed",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_ROAD_CONDITION,
        translation_key="road_condition",
        entity_registry_enabled_default=False,
    ),
)

FORECAST_SENSOR_DESCRIPTIONS: Final = (
    SensorEntityDescription(
        key=ATTR_FORECAST_CONDITION,
        translation_key="condition_forecast",
        has_entity_name=True,
        device_class=DEVICE_CLASS_TPL.format("condition"),
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_TEMP,
        translation_key="temperature_forecast",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_TEMP_LOW,
        translation_key="temperature_low_forecast",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_APPARENT_TEMP,
        translation_key="apparent_temperature_forecast",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_HUMIDITY,
        translation_key="humidity_forecast",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_PRESSURE,
        translation_key="pressure_forecast",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MMHG,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_PRECIPITATION_AMOUNT,
        translation_key="precipitation_forecast",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_SPEED,
        translation_key="wind_speed_forecast",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_GUST_SPEED,
        translation_key="wind_gust_speed_forecast",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_BEARING,
        translation_key="wind_bearing_forecast",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_WIND_BEARING_LABEL,
        translation_key="wind_bearing_label_forecast",
        icon="mdi:weather-windy",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_CLOUD_COVERAGE,
        translation_key="cloud_coverage_forecast",
        icon="mdi:weather-partly-cloudy",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_RAIN_AMOUNT,
        translation_key="rain_amount_forecast",
        icon="mdi:weather-rainy",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_SNOW_AMOUNT,
        translation_key="snow_amount_forecast",
        icon="mdi:weather-snowy",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_IS_STORM,
        translation_key="is_storm_forecast",
        icon="mdi:weather-lightning",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_GEOMAGNETIC_FIELD,
        translation_key="geomagnetic_field_forecast",
        icon="mdi:magnet-on",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_UV_INDEX,
        translation_key="uv_index_forecast",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_POLLEN_BIRCH,
        translation_key="pollen_birch_forecast",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_POLLEN_GRASS,
        translation_key="pollen_grass_forecast",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_POLLEN_RAGWEED,
        translation_key="pollen_ragweed_forecast",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_FORECAST_ROAD_CONDITION,
        translation_key="road_condition_forecast",
        entity_registry_enabled_default=False,
    ),
)
