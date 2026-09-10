"""The PiKVMCpuTempSensor class, which represents a CPU temperature sensor for PiKVM."""

import logging

from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import temperature

from .. import PiKVMDataUpdateCoordinator
from ..sensor import PiKVMBaseSensor
from ..utils import get_nested_value

_LOGGER = logging.getLogger(__name__)


# Function to convert temperature
def convert_temperature(value, from_unit, to_unit):
    """Convert temperature from one unit to another."""
    if from_unit == to_unit:
        return value
    return temperature.convert_temperature(value, from_unit, to_unit)


class PiKVMCpuTempSensor(PiKVMBaseSensor):
    """Representation of a PiKVM CPU temperature sensor."""

    def __init__(
        self,
        coordinator: PiKVMDataUpdateCoordinator,
        unique_id_base: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        name = f"{device_name} CPU Temp"
        super().__init__(
            coordinator,
            unique_id_base,
            "cpu_temp",
            name,
            "°C",
            "mdi:thermometer",
        )

    @property
    def state(self):
        """Return the state of the sensor in preferred units."""
        value = get_nested_value(self.coordinator.data, ["hw", "health", "temp", "cpu"])
        try:
            temp_value = float(value)
        except (TypeError, ValueError):
            return None  # or handle the error appropriately
        return self.coordinator.hass.config.units.temperature(
            temp_value, UnitOfTemperature.CELSIUS
        )

    @property
    def unit_of_measurement(self):
        """Return the preferred units of measure."""
        return self.coordinator.hass.config.units.temperature_unit

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return super().extra_state_attributes
