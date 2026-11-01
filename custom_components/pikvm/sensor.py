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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PiKVMConfigEntry
from .const import DOMAIN
from .coordinator import PiKVMDataUpdateCoordinator
from .entity import PiKVMEntity
from .utils import bytes_to_mb, get_nested_value, get_unique_id_base

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PiKVMSensorEntityDescription(SensorEntityDescription):
    """Describes a PiKVM sensor entity."""

    value_fn: Callable[[Any], StateType]
    attributes_fn: Callable[[Any], dict[str, Any]] | None = None
    available_fn: Callable[[Any], bool] | None = None


def _get_finite_float(data: Any, path: list[str]) -> float | None:
    """Extract and validate a finite float from nested telemetry data."""
    val = get_nested_value(data, path)
    if val is None:
        return None
    try:
        num = float(val)
        return num if math.isfinite(num) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _get_cpu_temp(data: Any) -> float | None:
    return _get_finite_float(data, ["hw", "health", "temp", "cpu"])


def _get_cpu_utilization(data: Any) -> float | None:
    return _get_finite_float(data, ["hw", "performance", "cpu", "utilization"])


def _get_memory_utilization(data: Any) -> float | None:
    return _get_finite_float(data, ["hw", "performance", "memory", "utilization"])


def _get_memory_attributes(data: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    available_bytes = get_nested_value(data, ["hw", "performance", "memory", "available"])
    total_bytes = get_nested_value(data, ["hw", "performance", "memory", "total"])
    if available_bytes is not None:
        attrs["available MB"] = bytes_to_mb(available_bytes)
    if total_bytes is not None:
        attrs["total MB"] = bytes_to_mb(total_bytes)
    return attrs


def _get_fan_speed(data: Any) -> int | None:
    val = get_nested_value(data, ["hw", "performance", "fan", "speed"])
    if val is None:
        val = get_nested_value(data, ["hw", "fan", "speed"])
    if val is None:
        return None
    try:
        num_int = int(val)
        num_float = float(num_int)
        if not math.isfinite(num_float) or not (0 <= num_float <= 100_000):
            return None
        return num_int
    except (ValueError, TypeError, OverflowError):
        return None


def _get_fan_attributes(data: Any) -> dict[str, Any]:
    fan_data = get_nested_value(data, ["hw", "performance", "fan"])
    if not isinstance(fan_data, Mapping):
        fan_data = get_nested_value(data, ["hw", "fan"])
    if isinstance(fan_data, Mapping):
        return dict(fan_data)
    return {}


def _get_msd_storage(data: Any) -> float | None:
    storage = get_nested_value(data, ["msd", "storage"])
    if not isinstance(storage, Mapping):
        return None
    total_raw = storage.get("total")
    avail_raw = (
        storage.get("available")
        if storage.get("available") is not None
        else storage.get("free")
    )
    if total_raw is None or avail_raw is None:
        return None
    try:
        total = float(total_raw)
        available = float(avail_raw)
        if not math.isfinite(total) or not math.isfinite(available) or total <= 0:
            return None
        used = max(0.0, total - available)
        return round(float((used / total) * 100), 2)
    except (ValueError, TypeError, OverflowError, ZeroDivisionError):
        return None


def _get_msd_storage_attributes(data: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    storage_data = get_nested_value(data, ["msd", "storage"])
    if not isinstance(storage_data, Mapping):
        return attrs

    total_raw = storage_data.get("total")
    avail_raw = (
        storage_data.get("available")
        if storage_data.get("available") is not None
        else storage_data.get("free")
    )

    if total_raw is not None:
        total_mb = bytes_to_mb(total_raw)
        if total_mb is not None:
            attrs["total_size_mb"] = round(total_mb, 2)

    if avail_raw is not None:
        free_mb = bytes_to_mb(avail_raw)
        if free_mb is not None:
            attrs["free_size_mb"] = round(free_mb, 2)

    if total_raw is not None and avail_raw is not None:
        try:
            total_num = float(total_raw)
            avail_num = float(avail_raw)
            if math.isfinite(total_num) and math.isfinite(avail_num):
                used = max(0.0, total_num - avail_num)
                used_mb = bytes_to_mb(used)
                if used_mb is not None:
                    attrs["used_size_mb"] = round(used_mb, 2)
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            pass

    val = _get_msd_storage(data)
    if val is not None:
        attrs["percent_used"] = val

    images = storage_data.get("images", {}) or {}
    if isinstance(images, Mapping) and images:
        if len(images) < 20:
            for image, details in images.items():
                if isinstance(details, Mapping):
                    size = details.get("size")
                    if size is not None:
                        attrs[str(image)] = size
        else:
            attrs["file count"] = len(images)
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
    coordinator: PiKVMDataUpdateCoordinator = (
        getattr(config_entry, "runtime_data", None)
        or (hass.data.get(DOMAIN, {}) or {})[config_entry.entry_id]
    )
    unique_id_base = get_unique_id_base(config_entry, coordinator)

    sensors = [
        PiKVMSensor(coordinator, unique_id_base, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    ent_reg = er.async_get(hass)
    valid_uids = {s.unique_id for s in sensors}
    if not unique_id_base.endswith("_unknown"):
        for ent_entry in er.async_entries_for_config_entry(
            ent_reg, config_entry.entry_id
        ):
            if ent_entry.domain == "sensor" and ent_entry.unique_id not in valid_uids:
                _LOGGER.info(
                    "Removing stale legacy sensor entity %s (unique_id: %s)",
                    ent_entry.entity_id,
                    ent_entry.unique_id,
                )
                ent_reg.async_remove(ent_entry.entity_id)

    async_add_entities(sensors)
    _LOGGER.debug("PiKVM sensors added to Home Assistant")
