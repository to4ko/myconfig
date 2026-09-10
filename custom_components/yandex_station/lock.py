import logging

from homeassistant.components.lock import LockEntity

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_CAPABILITIES = ("devices.capabilities.lock",)

async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        for instance in device["capabilities"]:
            if instance["type"] not in INCLUDE_CAPABILITIES:
                continue
            entities.append(YandexLock(quasar, device, instance))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexLock(LockEntity, YandexEntity):
    def internal_update(self, capabilities: dict, properties: dict):
        if value := capabilities.get("lock"):
            self._attr_is_locked = value == "closed"

    async def async_unlock(self):
        await self.device_action("lock", "open")

    async def async_lock(self):
        await self.device_action("lock", "closed")
