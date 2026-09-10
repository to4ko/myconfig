import logging

from homeassistant.components.ping import PingDataICMPLib
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from icmplib import async_ping
from sensor_state_data import SensorDeviceClass

from . import DOMAIN
from .utils import ARP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    host = entry.options.get(CONF_HOST)
    mac = entry.options.get(CONF_MAC)
    if host and not mac:
        await async_ping(host, count=1)
        if mac := ARP.get_mac(host):
            hass.config_entries.async_update_entry(
                entry, options={CONF_HOST: host, CONF_MAC: mac}
            )
    elif mac and not host:
        if host := ARP.get_host(mac):
            hass.config_entries.async_update_entry(
                entry, options={CONF_HOST: host, CONF_MAC: mac}
            )

    if host:
        async_add_entities([PingSensor(entry)], True)


class PingSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    ping: PingDataICMPLib = None

    def __init__(self, entry: ConfigEntry):
        self.host = entry.options[CONF_HOST]

        self._attr_name = entry.title + " RTT"
        self._attr_unique_id = entry.entry_id

        if mac := entry.options.get(CONF_MAC):
            self._attr_device_info = DeviceInfo(
                connections={(CONNECTION_NETWORK_MAC, mac)},
                identifiers={(DOMAIN, entry.entry_id)},
            )

    async def async_update(self):
        try:
            data = await async_ping(self.host, count=1, timeout=5)
            self._attr_native_value = round(data.rtts[0])
            self._attr_available = True
        except:
            self._attr_native_value = None
            self._attr_available = False
