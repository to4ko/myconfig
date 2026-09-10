import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant

from . import PythonEntity, compile_script

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
) -> None:
    if code := await hass.async_add_executor_job(compile_script, hass, config):
        async_add_entities([PythonBinarySensor(code, config)], True)


class PythonBinarySensor(BinarySensorEntity, PythonEntity):
    @property
    def state(self):
        return super().state

    @state.setter
    def state(self, value):
        self._attr_is_on = bool(value)
