"""Platform for PiKVM sensor integration."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PiKVMConfigEntry
from .coordinator import PiKVMDataUpdateCoordinator
from .entity import (
    PiKVMEntity,
    PiKVMEntityDescriptionMixin,
    async_cleanup_stale_entities,
)
from .utils import bytes_to_mb, ensure_device_info, get_nested_value, get_unique_id_base

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PiKVMSensorEntityDescription(
    SensorEntityDescription, PiKVMEntityDescriptionMixin
):
    """Describes a PiKVM sensor entity."""

    value_fn: Callable[[Any], StateType]


def _finite(val: float | None) -> float | None:
    """Return val if it is a finite float, otherwise None."""
    return val if val is not None and math.isfinite(val) else None


def _get_cpu_temp(data: Any) -> float | None:
    return _finite(info.cpu_temp) if (info := ensure_device_info(data)) else None


def _get_cpu_utilization(data: Any) -> float | None:
    return _finite(info.cpu_utilization) if (info := ensure_device_info(data)) else None


def _get_memory_utilization(data: Any) -> float | None:
    return (
        _finite(info.memory_utilization) if (info := ensure_device_info(data)) else None
    )


def _get_memory_attributes(data: Any) -> dict[str, Any]:
    if not (info := ensure_device_info(data)):
        return {}
    perf = info.hw.performance
    attrs: dict[str, Any] = {}
    if (avail := bytes_to_mb(perf.memory_available_bytes)) is not None:
        attrs["available MB"] = avail
    if (total := bytes_to_mb(perf.memory_total_bytes)) is not None:
        attrs["total MB"] = total
    return attrs


def _get_fan_speed(data: Any) -> int | None:
    if (info := ensure_device_info(data)) and (speed := info.fan_speed) is not None:
        return speed if 0 <= speed <= 100_000 else None
    return None


def _get_fan_attributes(data: Any) -> dict[str, Any]:
    for path in (["hw", "fan"], ["hw", "performance", "fan"]):
        if isinstance(fan := get_nested_value(data, path), Mapping) and any(
            v is not None for v in fan.values()
        ):
            return dict(fan)
    return {}


def _get_msd_storage(data: Any) -> float | None:
    return (
        _finite(info.msd.storage.percent_used)
        if (info := ensure_device_info(data))
        else None
    )


def _get_msd_storage_attributes(data: Any) -> dict[str, Any]:
    if not (info := ensure_device_info(data)):
        return {}
    storage = info.msd.storage
    attrs: dict[str, Any] = {}
    try:
        if (total_mb := _finite(storage.total_mb)) is not None:
            attrs["total_size_mb"] = total_mb
        if (free_mb := _finite(storage.free_mb)) is not None:
            attrs["free_size_mb"] = free_mb
        if (used_mb := _finite(storage.used_mb)) is not None:
            attrs["used_size_mb"] = used_mb
        if (pct := _finite(storage.percent_used)) is not None:
            attrs["percent_used"] = pct
    except OverflowError:
        return {}
    if storage.images:
        if len(storage.images) < 20:
            attrs.update(storage.images)
        else:
            attrs["file count"] = len(storage.images)
    return attrs


CPU_TEMP_SENSOR_DESCRIPTION = PiKVMSensorEntityDescription(
    key="cpu_temp",
    translation_key="cpu_temp",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=1,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_get_cpu_temp,
    available_fn=lambda data: _get_cpu_temp(data) is not None,
)

CPU_UTILIZATION_SENSOR_DESCRIPTION = PiKVMSensorEntityDescription(
    key="cpu_utilization",
    translation_key="cpu_utilization",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    suggested_display_precision=1,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_get_cpu_utilization,
    available_fn=lambda data: _get_cpu_utilization(data) is not None,
)

MEMORY_UTILIZATION_SENSOR_DESCRIPTION = PiKVMSensorEntityDescription(
    key="memory_utilization",
    translation_key="memory_utilization",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    suggested_display_precision=1,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_get_memory_utilization,
    attributes_fn=_get_memory_attributes,
    available_fn=lambda data: _get_memory_utilization(data) is not None,
)

FAN_SPEED_SENSOR_DESCRIPTION = PiKVMSensorEntityDescription(
    key="fan_speed",
    translation_key="fan_speed",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_get_fan_speed,
    attributes_fn=_get_fan_attributes,
    available_fn=lambda data: _get_fan_speed(data) is not None,
)

MSD_STORAGE_SENSOR_DESCRIPTION = PiKVMSensorEntityDescription(
    key="msd_storage",
    translation_key="msd_storage",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    suggested_display_precision=2,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_get_msd_storage,
    attributes_fn=_get_msd_storage_attributes,
    available_fn=lambda data: _get_msd_storage(data) is not None,
)

SENSOR_DESCRIPTIONS: tuple[PiKVMSensorEntityDescription, ...] = (
    CPU_TEMP_SENSOR_DESCRIPTION,
    CPU_UTILIZATION_SENSOR_DESCRIPTION,
    MEMORY_UTILIZATION_SENSOR_DESCRIPTION,
    FAN_SPEED_SENSOR_DESCRIPTION,
    MSD_STORAGE_SENSOR_DESCRIPTION,
)


class PiKVMSensor(PiKVMEntity, SensorEntity):
    """Representation of a PiKVM sensor."""

    entity_description: PiKVMSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PiKVMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PiKVM sensors from a config entry."""
    _LOGGER.debug("Setting up PiKVM sensors from config entry")
    coordinator: PiKVMDataUpdateCoordinator = config_entry.runtime_data
    unique_id_base = get_unique_id_base(config_entry, coordinator)

    sensors = [
        PiKVMSensor(coordinator, unique_id_base, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_cleanup_stale_entities(
        hass, config_entry, "sensor", unique_id_base, {s.unique_id for s in sensors}
    )

    async_add_entities(sensors)
    _LOGGER.debug("PiKVM sensors added to Home Assistant")
