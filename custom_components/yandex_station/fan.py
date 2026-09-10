import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.ventilation.fan",)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexFan(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexFan(FanEntity, YandexEntity):
    speeds: list[str] = []

    # https://developers.home-assistant.io/blog/2024/07/23/fan-fanentityfeatures-expanded
    if (MAJOR_VERSION, MINOR_VERSION) >= (2024, 8):
        _enable_turn_on_off_backwards_compatibility = False

    def internal_init(self, capabilities: dict, properties: dict):
        features = FanEntityFeature(0)

        if "on" in capabilities and (MAJOR_VERSION, MINOR_VERSION) >= (2024, 8):
            features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        if item := capabilities.get("fan_speed"):
            # keep speeds in the order the device reports them
            self.speeds = [i["value"] for i in item["modes"]]
            features |= FanEntityFeature.SET_SPEED

        if "oscillation" in capabilities:
            features |= FanEntityFeature.OSCILLATE

        self._attr_supported_features = features

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_is_on = capabilities["on"]

        if "fan_speed" in capabilities and self.speeds:
            value = capabilities["fan_speed"]
            self._attr_percentage = (
                ordered_list_item_to_percentage(self.speeds, value)
                if value in self.speeds
                else None
            )

        # report 0% while off, so the speed slider doesn't stick
        # at the last speed on a turned off fan
        if self._attr_is_on is False:
            self._attr_percentage = 0

        if "oscillation" in capabilities:
            self._attr_oscillating = capabilities["oscillation"]

    @property
    def speed_count(self) -> int:
        return len(self.speeds) or 1

    async def async_set_percentage(self, percentage: int):
        if percentage == 0:
            await self.device_action("on", False)
            return
        # sending fan_speed to a turned off device doesn't power it on
        if not self._attr_is_on:
            await self.device_action("on", True)
        mode = percentage_to_ordered_list_item(self.speeds, percentage)
        await self.device_action("fan_speed", mode)

    async def async_oscillate(self, oscillating: bool):
        await self.device_action("oscillation", oscillating)

    async def async_turn_on(
        self, percentage: int = None, preset_mode: str = None, **kwargs
    ):
        await self.device_action("on", True)
        if percentage is not None and self.speeds:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs):
        await self.device_action("on", False)
