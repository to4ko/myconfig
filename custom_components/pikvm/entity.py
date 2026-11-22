"""PiKVM entity base class."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PiKVMDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PiKVMEntityDescriptionMixin:
    """Mixin for PiKVM entity descriptions providing dynamic availability and attributes."""

    attributes_fn: Callable[[Any], dict[str, Any]] | None = None
    available_fn: Callable[[Any], bool] | None = None


def async_cleanup_stale_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    domain: str,
    unique_id_base: str,
    valid_uids: set[str | None],
) -> None:
    """Remove stale legacy entities for a platform when serial is known."""
    if unique_id_base.endswith("_unknown"):
        return
    ent_reg = er.async_get(hass)
    for ent_entry in er.async_entries_for_config_entry(
        ent_reg, config_entry.entry_id
    ):
        if ent_entry.domain == domain and ent_entry.unique_id not in valid_uids:
            _LOGGER.info(
                "Removing stale legacy %s entity %s (unique_id: %s)",
                domain,
                ent_entry.entity_id,
                ent_entry.unique_id,
            )
            ent_reg.async_remove(ent_entry.entity_id)


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
        description = getattr(self, "entity_description", None)
        if isinstance(description, PiKVMEntityDescriptionMixin) and description.available_fn is not None:
            return bool(description.available_fn(self.coordinator.data))
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {"ip": self.coordinator.url}
        description = getattr(self, "entity_description", None)
        if isinstance(description, PiKVMEntityDescriptionMixin) and description.attributes_fn is not None:
            extra = description.attributes_fn(self.coordinator.data)
            if extra and isinstance(extra, Mapping):
                attrs.update(extra)
        return attrs

