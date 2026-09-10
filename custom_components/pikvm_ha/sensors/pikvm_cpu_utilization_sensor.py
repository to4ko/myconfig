"""Module for the PiKVMCpuUtilizationSensor class.

Represents a sensor for monitoring the CPU utilization of a PiKVM device.
"""

import logging

from .. import PiKVMDataUpdateCoordinator
from ..sensor import PiKVMBaseSensor
from ..utils import get_nested_value

_LOGGER = logging.getLogger(__name__)


class PiKVMCpuUtilizationSensor(PiKVMBaseSensor):
    """Representation of a PiKVM CPU temperature sensor."""

    def __init__(
        self,
        coordinator: PiKVMDataUpdateCoordinator,
        unique_id_base,
        device_name,
    ) -> None:
        """Initialize the sensor."""
        name = f"{device_name} CPU Utilization"
        super().__init__(
            coordinator,
            unique_id_base,
            "cpu_utilization",
            name,
            "%",
            "mdi:cpu-64-bit",
        )

    @property
    def state(self):
        """Return the state of the sensor in preferred units."""
        return get_nested_value(
            self.coordinator.data, ["hw", "health", "cpu", "percent"]
        )

    @property
    def available(self):
        """Return True if the sensor data is available."""
        return "cpu" in get_nested_value(self.coordinator.data, ["hw", "health"], {})

    @property
    def unit_of_measurement(self):
        """Return the preferred units of measure."""
        return "%"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return super().extra_state_attributes
