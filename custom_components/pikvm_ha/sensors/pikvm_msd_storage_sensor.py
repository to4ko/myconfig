"""Support for PiKVM MSD storage sensor."""

import logging

from ..sensor import PiKVMBaseSensor
from ..utils import get_nested_value

_LOGGER = logging.getLogger(__name__)


class PiKVMSDStorageSensor(PiKVMBaseSensor):
    """Representation of a PiKVM MSD storage sensor."""

    def __init__(self, coordinator, unique_id_base, device_name) -> None:
        """Initialize the sensor."""
        name = f"{device_name} MSD Storage"
        super().__init__(
            coordinator,
            unique_id_base,
            "msd_storage",
            name,
            "%",
            "mdi:database",
        )

    @property
    def state(self):
        storage = get_nested_value(self.coordinator.data, ["msd", "storage"], {})
        total = storage.get("size")
        free = storage.get("free")
        if total is None or free is None or total <= 0:
            _LOGGER.debug("MSD storage data missing or invalid: %r", storage)
            return None  # marks sensor unavailable
        return round((free / total) * 100, 2)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        storage_data = get_nested_value(self.coordinator.data, ["msd", "storage"], {})
        images = storage_data.get("images", {}) or {}

        if storage_data:
            size = storage_data.get("size")
            free = storage_data.get("free")
            if size is not None:
                attributes["total_size_mb"] = round(size / (1024 * 1024), 2)
            if free is not None:
                attributes["free_size_mb"] = round(free / (1024 * 1024), 2)
            if size is not None and free is not None:
                attributes["used_size_mb"] = round((size - free) / (1024 * 1024), 2)
            state = self.state
            if state is not None:
                attributes["percent_free"] = state

        if images:
            if len(images) < 20:
                for image, details in images.items():
                    size = details.get("size")
                    if size is not None:
                        attributes[image] = size
            else:
                attributes["file count"] = len(images)
        return attributes
