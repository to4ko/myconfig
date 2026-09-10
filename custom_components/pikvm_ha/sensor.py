"""Platform for sensor integration."""

from collections.abc import Mapping
import logging

from voluptuous import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PiKVMEntity
from .utils import get_nested_value, get_unique_id_base

_LOGGER = logging.getLogger(__name__)


class PiKVMBaseSensor(PiKVMEntity):
    """Base class for a PiKVM sensor."""

    def __init__(
        self,
        coordinator,
        unique_id_base,
        sensor_type,
        name,
        unit=None,
        icon=None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, unique_id_base)
        self._attr_unique_id = f"{unique_id_base}_{sensor_type}"
        self._attr_name = name
        self._attr_unit_of_measurement = unit
        self._attr_icon = icon
        self._unique_id_base = unique_id_base
        self._sensor_type = sensor_type

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"ip": self.coordinator.url}

    @property
    def state(self) -> str | int | float | bool | None:
        """Return the state of the sensor."""
        raise NotImplementedError(
            "The state method must be implemented by the subclass."
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PiKVM sensors from a config entry."""
    _LOGGER.debug("Setting up PiKVM sensors from config entry")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    unique_id_base = get_unique_id_base(config_entry, coordinator)
    device_name = get_nested_value(
        coordinator.data, ["meta", "server", "host"], "pikvm"
    )

    # Use "pikvm" if the device name is "localhost.localdomain"
    if device_name == "localhost.localdomain":
        device_name = DOMAIN
    else:
        device_name = device_name.replace(".", "_")

    lazy_import_sensors()
    # List of sensors to create
    # List of sensors to create
    # Get sensor classes lazily
    sensor_classes = lazy_import_sensors()

    # List of sensors to create
    sensors = [
        sensor_classes["cpu_utilization"](coordinator, unique_id_base, device_name),
        sensor_classes["memory_utilization"](coordinator, unique_id_base, device_name),
        sensor_classes["cpu_temp"](coordinator, unique_id_base, device_name),
        sensor_classes["fan_speed"](coordinator, unique_id_base, device_name),
        sensor_classes["throttling"](coordinator, unique_id_base, device_name),
        sensor_classes["msd_enabled"](coordinator, unique_id_base, device_name),
        sensor_classes["msd_drive"](coordinator, unique_id_base, device_name),
        sensor_classes["msd_storage"](coordinator, unique_id_base, device_name),
    ]

    # Dynamically create sensors for extras
    extras = get_nested_value(coordinator.data, ["extras"], {})
    for extra_name, extra_data in extras.items():
        sensors.append(
            sensor_classes["extra"](
                coordinator,
                extra_name,
                extra_data,
                unique_id_base,
                device_name,
            )
        )

    async_add_entities(sensors, True)
    _LOGGER.debug("%s PiKVM sensors added to Home Assistant", device_name)


# pylint: disable=import-outside-toplevel
def lazy_import_sensors():
    """Lazy load the sensor classes."""
    from .sensors.pikvm_cpu_temp_sensor import PiKVMCpuTempSensor
    from .sensors.pikvm_cpu_utilization_sensor import PiKVMCpuUtilizationSensor
    from .sensors.pikvm_extra_sensor import PiKVMExtraSensor
    from .sensors.pikvm_fan_speed_sensor import PiKVMFanSpeedSensor
    from .sensors.pikvm_memory_utilization_sensor import PiKVMMemoryUtilizationSensor
    from .sensors.pikvm_msd_drive_sensor import PiKVMSDDriveSensor
    from .sensors.pikvm_msd_enabled_sensor import PiKVMSDEnabledSensor
    from .sensors.pikvm_msd_storage_sensor import PiKVMSDStorageSensor
    from .sensors.pikvm_throttling_sensor import PiKVMThrottlingSensor

    return {
        "cpu_temp": PiKVMCpuTempSensor,
        "cpu_utilization": PiKVMCpuUtilizationSensor,
        "extra": PiKVMExtraSensor,
        "fan_speed": PiKVMFanSpeedSensor,
        "memory_utilization": PiKVMMemoryUtilizationSensor,
        "msd_drive": PiKVMSDDriveSensor,
        "msd_enabled": PiKVMSDEnabledSensor,
        "msd_storage": PiKVMSDStorageSensor,
        "throttling": PiKVMThrottlingSensor,
    }
