"""Module for PiKVM extra sensor integration."""

from homeassistant.const import EntityCategory

from ..sensor import PiKVMBaseSensor
from ..utils import get_nested_value


class PiKVMExtraSensor(PiKVMBaseSensor):
    """Representation of a PiKVM extra sensor."""

    ICONS = {
        "ipmi": "mdi:network",
        "janus": "mdi:web",
        "janus_static": "mdi:web",
        "vnc": "mdi:monitor",
        "webterm": "mdi:console",
    }

    def __init__(self, coordinator, name, data, unique_id_base, device_name) -> None:
        """Initialize the sensor."""
        icon = self.ICONS.get(name, "mdi:information")
        sensor_name = f"{device_name} {name.capitalize()}"
        super().__init__(
            coordinator,
            unique_id_base,
            f"extra_{name}",
            sensor_name,
            icon=icon,
        )
        self._extra_name = name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        """Return the state of the sensor."""
        extra_data = get_nested_value(
            self.coordinator.data, ["extras", self._extra_name], {}
        )
        return extra_data.get("enabled", False)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        extra_data = get_nested_value(
            self.coordinator.data, ["extras", self._extra_name], {}
        )
        attributes.update(extra_data)
        return attributes
