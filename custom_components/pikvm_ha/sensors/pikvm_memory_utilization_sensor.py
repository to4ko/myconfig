"""Represents a sensor for monitoring memory utilization on a PiKVM device."""

import logging
from typing import NamedTuple

from .. import PiKVMDataUpdateCoordinator
from ..sensor import PiKVMBaseSensor
from ..utils import bytes_to_mb, get_nested_value

_LOGGER = logging.getLogger(__name__)


class PiKVMResponse(NamedTuple):
    """Represents a PiKVM response."""

    success: bool
    model: str
    serial: str
    name: str
    error: str


class PiKVMMemoryUtilizationSensor(PiKVMBaseSensor):
    """Representation of a PiKVM CPU temperature sensor."""

    def __init__(
        self,
        coordinator: PiKVMDataUpdateCoordinator,
        unique_id_base,
        device_name,
    ) -> None:
        """Initialize the sensor."""
        name = f"{device_name} Memory Utilization"
        super().__init__(
            coordinator,
            unique_id_base,
            "memory_utilization",
            name,
            "%",
            "mdi:memory",
        )

    @property
    def state(self):
        """Return the state of the sensor in preferred units."""
        return get_nested_value(
            self.coordinator.data, ["hw", "health", "mem", "percent"]
        )

    @property
    def available(self):
        """Return True if the sensor data is available."""
        return "mem" in get_nested_value(self.coordinator.data, ["hw", "health"], {})

    @property
    def unit_of_measurement(self):
        """Return the preferred units of measure."""
        return "%"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        available_bytes = get_nested_value(
            self.coordinator.data, ["hw", "health", "mem", "available"]
        )
        total_bytes = get_nested_value(
            self.coordinator.data, ["hw", "health", "mem", "total"]
        )
        attributes["available MB"] = bytes_to_mb(available_bytes)
        attributes["total MB"] = bytes_to_mb(total_bytes)
        return attributes
