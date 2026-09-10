"""Support for PiKVM MSD enabled sensor."""

from homeassistant.const import EntityCategory

from ..sensor import PiKVMBaseSensor


from ..utils import get_nested_value


class PiKVMSDEnabledSensor(PiKVMBaseSensor):
    """Representation of a PiKVM MSD enabled sensor."""

    def __init__(self, coordinator, unique_id_base, device_name) -> None:
        """Initialize the sensor."""
        name = f"{device_name} MSD Enabled"
        super().__init__(
            coordinator,
            unique_id_base,
            "msd_enabled",
            name,
            icon="mdi:check-circle",
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> bool:
        """Return the state of the sensor."""
        return get_nested_value(self.coordinator.data, ["msd", "enabled"], False)
