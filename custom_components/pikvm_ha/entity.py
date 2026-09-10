"""PiKVM entity base class."""

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PiKVMDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class PiKVMEntity(CoordinatorEntity):
    """Base class for a PiKVM entity."""

    coordinator: PiKVMDataUpdateCoordinator

    def __init__(
        self, coordinator: PiKVMDataUpdateCoordinator, unique_id_base: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id_base = unique_id_base
