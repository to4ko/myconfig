import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import PythonEntity, compile_script

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
) -> None:
    if code := await hass.async_add_executor_job(compile_script, hass, config):
        async_add_entities([PythonSensor(code, config)], True)


class PythonSensor(SensorEntity, PythonEntity):
    def __init__(self, code, config: dict):
        PythonEntity.__init__(self, code, config)

        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def state(self):
        return super().state

    @state.setter
    def state(self, value):
        self._attr_native_value = value
