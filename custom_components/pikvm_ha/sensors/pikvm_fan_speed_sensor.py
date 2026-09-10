"""Support for PiKVM fan speed sensor."""

from ..sensor import PiKVMBaseSensor
from ..utils import get_nested_value


class PiKVMFanSpeedSensor(PiKVMBaseSensor):
    """Representation of a PiKVM fan speed sensor."""

    def __init__(self, coordinator, unique_id_base, device_name) -> None:
        """Initialize the sensor."""
        name = f"{device_name} Fan Speed"
        super().__init__(coordinator, unique_id_base, "fan_speed", name, icon="mdi:fan")

        # Ensure fan_data is not None
        self.hall_available = False
        if coordinator.data and coordinator.data.get("fan"):
            fan_data = coordinator.data.get("fan", {}).get("state", {})
            if fan_data:
                hall_data = fan_data.get("hall", {})
                if hall_data:
                    self.hall_available = hall_data.get("available", False)

        # Set the unit of measurement based on hall availability
        self._attr_unit_of_measurement = "RPM" if self.hall_available else "%"

    @property
    def available(self):
        """Return True if the sensor data is available."""
        fan = get_nested_value(self.coordinator.data, ["fan"], {})
        return "state" in fan

    @property
    def state(self):
        """Return the state of the sensor."""
        fan_state = get_nested_value(self.coordinator.data, ["fan", "state"], {})
        if not fan_state:
            return None

        if self.hall_available:
            hall_data = fan_state.get("hall", {})
            return hall_data.get("rpm", None) if hall_data else None

        fan_data = fan_state.get("fan", {})
        return fan_data.get("speed", None) if fan_data else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        fan_state = get_nested_value(self.coordinator.data, ["fan", "state"], {})
        if fan_state:
            attributes.update(fan_state)
        return attributes
