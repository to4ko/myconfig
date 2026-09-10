from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_MAC, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from . import utils

DOMAIN = "lan_diagnostics"
PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def update_device_mac(call: ServiceCall) -> dict:
        device_id = call.data.get(CONF_DEVICE_ID)
        mac = call.data.get(CONF_MAC)
        if primary_domains := call.data.get("primary_domains"):
            primary_domains = primary_domains.split(",")

        if device_id and mac:
            return utils.update_device_mac(hass, device_id, mac)

        if device_id:
            return utils.update_device(hass, device_id, primary_domains)

        return utils.update_devices(hass, primary_domains)

    hass.services.async_register(
        DOMAIN,
        "update_device_mac",
        update_device_mac,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
