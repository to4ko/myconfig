"""PiKVM entity base class."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PiKVMDataUpdateCoordinator


class PiKVMEntity(CoordinatorEntity[PiKVMDataUpdateCoordinator]):
    """Base class for a PiKVM entity."""

    _attr_has_entity_name = True
    _attr_unique_id_base: str

    def __init__(
        self,
        coordinator: PiKVMDataUpdateCoordinator,
        unique_id_base: str,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id_base = unique_id_base
        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{unique_id_base}_{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not (super().available and self.coordinator.data is not None):
            return False
        available_fn = getattr(
            getattr(self, "entity_description", None), "available_fn", None
        )
        if available_fn is not None:
            return bool(available_fn(self.coordinator.data))
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {"ip": self.coordinator.url}
        attributes_fn = getattr(
            getattr(self, "entity_description", None), "attributes_fn", None
        )
        if attributes_fn is not None:
            extra = attributes_fn(self.coordinator.data)
            if extra and isinstance(extra, Mapping):
                attrs.update(extra)
        return attrs
