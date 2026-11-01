"""Platform for PiKVM binary sensor integration."""

from __future__ import annotations

import logging
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PiKVMConfigEntry
from .const import DOMAIN, LEGACY_DOMAIN
from .coordinator import PiKVMDataUpdateCoordinator
from .entity import PiKVMEntity
from .utils import get_nested_value, get_unique_id_base

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PiKVMBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a PiKVM binary sensor entity."""

    is_on_fn: Callable[[Any], bool | None]
    attributes_fn: Callable[[Any], dict[str, Any]] | None = None
    available_fn: Callable[[Any], bool] | None = None


def _is_throttling_on(data: Any) -> bool:
    """Return True if PiKVM hardware is currently throttled."""
    raw_flags = get_nested_value(data, ["hw", "health", "throttling", "raw_flags"])
    if isinstance(raw_flags, (int, float)) and not isinstance(raw_flags, bool):
        try:
            return int(raw_flags) > 0
        except (ValueError, TypeError, OverflowError):
            return False
    return False


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
        is_on_fn=lambda data: bool(get_nested_value(data, ["msd", "is_enabled"], False)),
        available_fn=lambda data: isinstance(get_nested_value(data, ["msd"]), Mapping),
    ),
    PiKVMBinarySensorEntityDescription(
        key="msd_drive",
        translation_key="msd_drive",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: bool(
            get_nested_value(data, ["msd", "drive", "is_mounted"], False)
        ),
        attributes_fn=_get_msd_drive_attributes,
        available_fn=lambda data: isinstance(
            get_nested_value(data, ["msd", "drive"]), Mapping
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PiKVMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PiKVM binary sensors from a config entry."""
    coordinator: PiKVMDataUpdateCoordinator = (
        getattr(config_entry, "runtime_data", None)
        or (hass.data.get(DOMAIN, {}) or {})[config_entry.entry_id]
    )
    unique_id_base = get_unique_id_base(config_entry, coordinator)

    _async_cleanup_legacy_sensors(hass, unique_id_base, coordinator.data)

    entities: list[BinarySensorEntity] = [
        PiKVMBinarySensor(coordinator, unique_id_base, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    extras = get_nested_value(coordinator.data, ["extras"], {})
    if isinstance(extras, Mapping):
        for extra_name, extra_data in extras.items():
            entities.append(
                PiKVMExtraBinarySensor(
                    coordinator=coordinator,
                    extra_name=extra_name,
                    extra_data=extra_data if isinstance(extra_data, dict) else {},
                    unique_id_base=unique_id_base,
                )
            )

    ent_reg = er.async_get(hass)
    valid_uids = {e.unique_id for e in entities}
    if not unique_id_base.endswith("_unknown"):
        for ent_entry in er.async_entries_for_config_entry(
            ent_reg, config_entry.entry_id
        ):
            if (
                ent_entry.domain == "binary_sensor"
                and ent_entry.unique_id not in valid_uids
            ):
                _LOGGER.info(
                    "Removing stale legacy binary_sensor entity %s (unique_id: %s)",
                    ent_entry.entity_id,
                    ent_entry.unique_id,
                )
                ent_reg.async_remove(ent_entry.entity_id)

    async_add_entities(entities)


def _async_cleanup_legacy_sensors(
    hass: HomeAssistant,
    unique_id_base: str,
    coordinator_data: Any,
) -> None:
    """Remove legacy sensor entities from entity registry during migration to binary_sensor."""
    if unique_id_base.endswith("_unknown"):
        return
    ent_reg = er.async_get(hass)
    migrated_keys = ["throttling", "msd_enabled", "msd_drive"]
    extras = get_nested_value(coordinator_data, ["extras"], {})
    if isinstance(extras, Mapping):
        migrated_keys.extend([f"extra_{name}" for name in extras])

    for key in migrated_keys:
        old_unique_id = f"{unique_id_base}_{key}"
        for dom in (DOMAIN, LEGACY_DOMAIN):
            old_entity_id = ent_reg.async_get_entity_id("sensor", dom, old_unique_id)
            if old_entity_id:
                _LOGGER.info(
                    "Migrating legacy sensor %s to binary_sensor platform (unique_id: %s)",
                    old_entity_id,
                    old_unique_id,
                )
                ent_reg.async_remove(old_entity_id)


class PiKVMBinarySensor(PiKVMEntity, BinarySensorEntity):
    """Representation of a PiKVM binary sensor."""

    entity_description: PiKVMBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)


class PiKVMExtraBinarySensor(PiKVMBinarySensor):
    """Representation of a PiKVM extra service binary sensor."""

    def __init__(
        self,
        coordinator: PiKVMDataUpdateCoordinator,
        extra_name: str,
        extra_data: dict[str, Any] | None = None,
        unique_id_base: str = "",
        device_name: str | None = None,
    ) -> None:
        """Initialize the extra service binary sensor."""
        self._extra_name = extra_name
        super().__init__(
            coordinator,
            unique_id_base,
            PiKVMBinarySensorEntityDescription(
                key=f"extra_{extra_name}",
                translation_key=f"extra_{extra_name}",
                device_class=BinarySensorDeviceClass.RUNNING,
                entity_category=EntityCategory.DIAGNOSTIC,
                is_on_fn=lambda data: bool(
                    d.get("is_running", False)
                    if isinstance(
                        d := get_nested_value(data, ["extras", extra_name]), Mapping
                    )
                    else False
                ),
                available_fn=lambda data: (
                    isinstance(extras := get_nested_value(data, ["extras"]), Mapping)
                    and extra_name in extras
                ),
                attributes_fn=lambda data: (
                    dict(d)
                    if isinstance(
                        d := get_nested_value(data, ["extras", extra_name]), Mapping
                    )
                    else {}
                ),
            ),
        )
