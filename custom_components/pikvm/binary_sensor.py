"""Platform for PiKVM binary sensor integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PiKVMConfigEntry
from .coordinator import PiKVMDataUpdateCoordinator
from .entity import (
    PiKVMEntity,
    PiKVMEntityDescriptionMixin,
    async_cleanup_stale_entities,
)
from .utils import ensure_device_info, get_nested_value, get_unique_id_base

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PiKVMBinarySensorEntityDescription(
    BinarySensorEntityDescription, PiKVMEntityDescriptionMixin
):
    """Describes a PiKVM binary sensor entity."""

    is_on_fn: Callable[[Any], bool | None]


def _is_throttling_on(data: Any) -> bool:
    """Return True if PiKVM hardware is currently throttled."""
    return bool(info.is_throttled) if (info := ensure_device_info(data)) else False


def _get_throttling_attributes(data: Any) -> dict[str, Any]:
    """Return attributes dictionary for throttling binary sensor."""
    throttling = get_nested_value(data, ["hw", "health", "throttling"])
    return dict(throttling) if isinstance(throttling, Mapping) else {}


def _is_throttling_available(data: Any) -> bool:
    """Return True if throttling telemetry is available."""
    return isinstance(get_nested_value(data, ["hw", "health"]), Mapping)


def _get_msd_drive_attributes(data: Any) -> dict[str, Any]:
    """Return attributes dictionary for MSD drive binary sensor."""
    drive = get_nested_value(data, ["msd", "drive"])
    return dict(drive) if isinstance(drive, Mapping) else {}


def _is_extra_running(extra_data: Mapping[str, Any]) -> bool:
    """Return True if a PiKVM extra service is running."""
    if (started := extra_data.get("started")) is not None:
        return bool(started)
    if (is_running := extra_data.get("is_running")) is not None:
        return bool(is_running)
    return bool(extra_data.get("enabled", False))


def _make_extra_description(extra_name: str) -> PiKVMBinarySensorEntityDescription:
    """Create a binary sensor description for a PiKVM extra service."""
    return PiKVMBinarySensorEntityDescription(
        key=f"extra_{extra_name}",
        translation_key=f"extra_{extra_name}",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            _is_extra_running(d)
            if (info := ensure_device_info(data))
            and isinstance(d := info.extras.get(extra_name), Mapping)
            else False
        ),
        available_fn=lambda data: bool(
            (info := ensure_device_info(data))
            and isinstance(get_nested_value(data, ["extras"]), Mapping)
            and extra_name in info.extras
        ),
        attributes_fn=lambda data: (
            dict(d)
            if (info := ensure_device_info(data))
            and isinstance(d := info.extras.get(extra_name), Mapping)
            else {}
        ),
    )


BINARY_SENSOR_DESCRIPTIONS: tuple[PiKVMBinarySensorEntityDescription, ...] = (
    PiKVMBinarySensorEntityDescription(
        key="throttling",
        translation_key="throttling",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_throttling_on,
        attributes_fn=_get_throttling_attributes,
        available_fn=_is_throttling_available,
    ),
    PiKVMBinarySensorEntityDescription(
        key="msd_enabled",
        translation_key="msd_enabled",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            bool(info.msd.is_enabled) if (info := ensure_device_info(data)) else False
        ),
        available_fn=lambda data: isinstance(get_nested_value(data, ["msd"]), Mapping),
    ),
    PiKVMBinarySensorEntityDescription(
        key="msd_drive",
        translation_key="msd_drive",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            bool(info.msd.drive.connected or info.msd.drive.is_mounted)
            if (info := ensure_device_info(data))
            else False
        ),
        attributes_fn=_get_msd_drive_attributes,
        available_fn=lambda data: isinstance(
            get_nested_value(data, ["msd", "drive"]), Mapping
        ),
    ),
)


class PiKVMBinarySensor(PiKVMEntity, BinarySensorEntity):
    """Representation of a PiKVM binary sensor."""

    entity_description: PiKVMBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PiKVMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PiKVM binary sensors from a config entry."""
    coordinator: PiKVMDataUpdateCoordinator = config_entry.runtime_data
    unique_id_base = get_unique_id_base(config_entry, coordinator)
    info = ensure_device_info(coordinator.data)
    extras = (
        info.extras
        if info and isinstance(get_nested_value(coordinator.data, ["extras"]), Mapping)
        else {}
    )

    descriptions = [
        *BINARY_SENSOR_DESCRIPTIONS,
        *(_make_extra_description(name) for name in extras),
    ]
    entities = [
        PiKVMBinarySensor(coordinator, unique_id_base, description)
        for description in descriptions
    ]

    async_cleanup_stale_entities(
        hass,
        config_entry,
        "binary_sensor",
        unique_id_base,
        {e.unique_id for e in entities},
    )

    async_add_entities(entities)
