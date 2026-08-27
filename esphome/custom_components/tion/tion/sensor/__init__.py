import esphome.codegen as cg
from esphome.components import sensor
from esphome.const import (
    CONF_ACCURACY_DECIMALS,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_DURATION,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLUME_FLOW_RATE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_CELSIUS,
    UNIT_CUBIC_METER,
    UNIT_CUBIC_METER_PER_HOUR,
    UNIT_KILOWATT,
    UNIT_PERCENT,
    UNIT_SECOND,
    UNIT_WATT,
)

from .. import cgp, new_pc, tion_ns

TionSensor = tion_ns.class_("TionSensor", sensor.Sensor, cg.Component)

UNIT_DAYS = "d"

PC = new_pc(
    {
        "fan_speed": {
            CONF_ICON: cgp.ICON_FAN,
            CONF_ACCURACY_DECIMALS: 0,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "outdoor_temperature": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_ICON: cgp.ICON_THERMOMETER,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CELSIUS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "current_temperature": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_ICON: cgp.ICON_HOME_THERMOMETER,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CELSIUS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "target_temperature": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_ICON: cgp.ICON_THERMOMETER_AUTO,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CELSIUS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "productivity": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_VOLUME_FLOW_RATE,
            CONF_ICON: cgp.ICON_WEATHER_WINDY,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CUBIC_METER_PER_HOUR,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "heater_var": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_UNIT_OF_MEASUREMENT: UNIT_PERCENT,
            CONF_ICON: cgp.ICON_FLASH_OUTLINE,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "heater_power": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_POWER,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_UNIT_OF_MEASUREMENT: UNIT_WATT,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "fan_power": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_POWER,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_UNIT_OF_MEASUREMENT: UNIT_WATT,
            CONF_ACCURACY_DECIMALS: 2,
        },
        "power": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_POWER,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_UNIT_OF_MEASUREMENT: UNIT_KILOWATT,
            CONF_ACCURACY_DECIMALS: 2,
        },
        "work_time": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_DURATION,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            CONF_UNIT_OF_MEASUREMENT: UNIT_SECOND,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "work_time_days": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            CONF_UNIT_OF_MEASUREMENT: UNIT_DAYS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "fan_time": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_DURATION,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            CONF_UNIT_OF_MEASUREMENT: UNIT_SECOND,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "fan_time_days": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            CONF_UNIT_OF_MEASUREMENT: UNIT_DAYS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "filter_time_left": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_ICON: "mdi:filter",
            CONF_DEVICE_CLASS: DEVICE_CLASS_DURATION,
            CONF_UNIT_OF_MEASUREMENT: UNIT_SECOND,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "filter_time_left_days": {
            # (24 * 3600)
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_ICON: "mdi:filter",
            CONF_UNIT_OF_MEASUREMENT: UNIT_DAYS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "airflow": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            CONF_ICON: cgp.ICON_WEATHER_WINDY,
            CONF_ACCURACY_DECIMALS: 2,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CUBIC_METER,
        },
        "airflow_counter": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            CONF_ICON: cgp.ICON_WEATHER_WINDY,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "pcb_ctl_temperature": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CELSIUS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "pcb_pwr_temperature": {
            CONF_ENTITY_CATEGORY: ENTITY_CATEGORY_DIAGNOSTIC,
            CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            CONF_UNIT_OF_MEASUREMENT: UNIT_CELSIUS,
            CONF_ACCURACY_DECIMALS: 0,
        },
        "boost_time_left": {
            CONF_DEVICE_CLASS: DEVICE_CLASS_DURATION,
            CONF_ICON: cgp.ICON_CLOCK_END,
            CONF_UNIT_OF_MEASUREMENT: UNIT_SECOND,
            CONF_ACCURACY_DECIMALS: 0,
        },
        # aliases
        "fan": "fan_speed",
        "speed": "fan_speed",
        "indoor_temperature": "current_temperature",
    }
)


CONFIG_SCHEMA = PC.sensor_schema(TionSensor)


async def to_code(config: dict):
    await PC.new_sensor(config)
