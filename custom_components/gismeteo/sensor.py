#  Copyright (c) 2019-2024, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
"""The Gismeteo component.

For more details about this platform, please refer to the documentation at
https://github.com/Limych/ha-gismeteo/
"""

from datetime import date, datetime
from decimal import Decimal
import logging

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.weather import ATTR_FORECAST_CONDITION
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType

from . import GismeteoDataUpdateCoordinator, deslugify
from .const import (
    ATTRIBUTION,
    CONF_ADD_SENSORS,
    CONF_FORECAST_DAYS,
    COORDINATOR,
    DOMAIN,
    DOMAIN_YAML,
    FORECAST_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    ForecastMode,
)
from .entity import GismeteoEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})


def _gen_entities(
    location_name: str,
    coordinator: GismeteoDataUpdateCoordinator,
    config: ConfigType,
):
    """Generate entities."""
    entities = [
        GismeteoSensor(coordinator, desc, location_name) for desc in SENSOR_DESCRIPTIONS
    ]

    days = config.get(CONF_FORECAST_DAYS)
    if days is not None:
        for day in range(days + 1):
            entities.extend(
                [
                    GismeteoSensor(coordinator, desc, location_name, day)
                    for desc in FORECAST_SENSOR_DESCRIPTIONS
                ]
            )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Add Gismeteo sensor entities."""
    entities = []
    if config_entry.source == SOURCE_IMPORT:
        # Setup from configuration.yaml
        for uid, config in hass.data[DOMAIN_YAML].items():
            if config is None:
                config = {}
            if not config.get(CONF_ADD_SENSORS):
                continue  # pragma: no cover

            location_name = config.get(CONF_NAME, deslugify(uid))
            coordinator = hass.data[DOMAIN][uid][COORDINATOR]

            entities.extend(_gen_entities(location_name, coordinator, config))

    else:
        # Setup from config entry
        config = config_entry.data.copy()  # type: ConfigType
        config.update(config_entry.options)

        if not config.get(CONF_ADD_SENSORS):
            return  # pragma: no cover

        location_name = config[CONF_NAME]
        coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

        entities.extend(_gen_entities(location_name, coordinator, config))

    async_add_entities(entities)


class GismeteoSensor(GismeteoEntity, SensorEntity):
    """Implementation of an Gismeteo sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GismeteoDataUpdateCoordinator,
        description: SensorEntityDescription,
        location_name: str,
        day: int | None = None,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator, location_name)

        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.unique_id}-{description.key}"
            if day is None
            else f"{coordinator.unique_id}-{day}-{description.key}"
        ).lower()
        self._attr_translation_placeholders = {
            "location_name": location_name,
            "type": description.key,
            "day": day,
        }
        self._attr_extra_state_attributes = self._gismeteo.attributes

        self._day = day

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        try:

            if self._day is None:
                res = getattr(self._gismeteo, self.entity_description.key)()
            else:
                forecast = self._gismeteo.forecast_data(self._day, ForecastMode.DAILY)
                if self.entity_description.key == ATTR_FORECAST_CONDITION:
                    res = getattr(self._gismeteo, self.entity_description.key)(
                        forecast, ForecastMode.DAILY
                    )
                else:
                    res = getattr(self._gismeteo, self.entity_description.key)(forecast)

            return res

        except KeyError:  # pragma: no cover
            _LOGGER.warning(
                "Condition is currently not available: %s", self.entity_description.key
            )
            return None
