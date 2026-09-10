"""Support for PiKVM throttling sensor."""

from ..sensor import PiKVMBaseSensor
from ..utils import get_nested_value


class PiKVMThrottlingSensor(PiKVMBaseSensor):
    """Representation of a PiKVM throttling sensor."""

    def __init__(self, coordinator, unique_id_base, device_name) -> None:
        """Initialize the sensor."""
        name = f"{device_name} Throttling"
        super().__init__(
            coordinator,
            unique_id_base,
            "throttling",
            name,
            icon="mdi:alert",
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        health = get_nested_value(self.coordinator.data, ["hw", "health"], {})
        return health.get("throttling", {}).get("raw_flags", 0)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        health = get_nested_value(self.coordinator.data, ["hw", "health"], {})
        throttling_data = health.get("throttling", {})
        flattened_data = {}
        for key, value in throttling_data.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            flattened_data[f"{sub_key}.{sub_sub_key}"] = sub_sub_value
                    else:
                        flattened_data[f"{key}.{sub_key}"] = sub_value
            else:
                flattened_data[key] = value
        return flattened_data
