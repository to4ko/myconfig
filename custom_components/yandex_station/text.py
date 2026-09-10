import re

from homeassistant.components.text import TextEntity

from .core.entity import YandexEntity
from .hass import hass_utils

INCLUDE_TYPES = (
    "devices.types.smart_speaker.yandex.station.orion",
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexText(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


class YandexText(TextEntity, YandexEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        pass

    def internal_update(self, capabilities: dict, properties: dict):
        if "led_array" in capabilities:
            array: list[int] = capabilities["led_array"]
            self._attr_native_value = ",".join(str(i) for i in array)

    async def async_set_value(self, value: str) -> None:
        array: list[int] = [int(i) for i in re.findall(r"\d+", value)]
        await self.device_action("led_array", array)
