import platform
import re
import subprocess
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    CONNECTION_ZIGBEE,
    DeviceEntry,
)
from homeassistant.helpers.entity_component import DATA_INSTANCES


class ARPList:
    cache: dict[str, str] = None  # {host: mac} pairs
    timeout: float = 0

    def __init__(self):
        if platform.system() == "Windows":
            # 0.0.0.0 255.255.255.255 ff-ff-ff-ff-ff-ff
            reg = re.compile(r"([0-9.]{7,15}) +([0-9a-f:]{17}) +dynamic")
            self.parse = lambda s: reg.findall(s.replace("-", ":").lower())
        else:
            # 0.0.0.0 255.255.255.255 0:0:0:0:0:0
            reg = re.compile(r"\(([0-9.]{7,15})\) at ([0-9a-f:]{11,17})")
            self.parse = lambda s: ((k, self.format_mac(v)) for k, v in reg.findall(s))

    @staticmethod
    def format_mac(mac: str) -> str:
        return ":".join(i if len(i) == 2 else f"0{i}" for i in mac.split(":"))

    def update(self):
        if time.time() < self.timeout:
            return

        stdout = subprocess.check_output(["arp", "-a"], timeout=5).decode()
        self.cache = dict(self.parse(stdout))
        self.timeout = time.time() + 60

    def get_mac(self, host: str) -> str | None:
        self.update()
        return self.cache.get(host)

    def get_host(self, mac: str) -> str | None:
        self.update()
        mac = dr.format_mac(mac)
        return next((k for k, v in self.cache.items() if v == mac), None)


ARP = ARPList()
RE_IP = re.compile(r"\b[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b")


def get_config_entry_mac(hass: HomeAssistant, device: DeviceEntry) -> tuple | None:
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        for host in RE_IP.findall(f"{entry.data}{entry.options}"):
            if mac := ARP.get_mac(host):
                return host, mac
    return None


def get_entity(hass: HomeAssistant, device_id: str, domain: str) -> str | None:
    entries = er.async_get(hass).entities.get_entries_for_device_id(device_id)
    entry = next(i for i in entries if i.domain == domain)
    return hass.data[DATA_INSTANCES][domain].get_entity(entry.entity_id)


def get_cast_mac(hass: HomeAssistant, device: DeviceEntry) -> tuple | None:
    try:
        entity = get_entity(hass, device.id, "media_player")
        info = getattr(entity, "_cast_info")
        if info.is_audio_group:
            return None
        host = info.cast_info.host
        return host, ARP.get_mac(host)
    except:
        return None


def get_yandex_station_mac(hass: HomeAssistant, device: DeviceEntry) -> tuple | None:
    try:
        entity = get_entity(hass, device.id, "media_player")
        host = getattr(entity, "device")["host"]
        return host, ARP.get_mac(host)
    except:
        return None


def merge_devices(hass: HomeAssistant, primary: DeviceEntry, second: DeviceEntry):
    ent_reg = er.async_get(hass)
    # move entities to new device
    entries = ent_reg.entities.get_entries_for_device_id(second.id)
    for entry in entries:
        ent_reg.async_update_entity(entry.entity_id, device_id=primary.id)

    dev_reg = dr.async_get(hass)
    # disable second device
    dev_reg.async_update_device(second.id, new_identifiers=set())
    dev_reg.async_remove_device(second.id)
    # move config entry and identifiers to primary device
    dev_reg.async_update_device(
        primary.id,
        add_config_entry_id=second.primary_config_entry,
        merge_identifiers=second.identifiers,
    )


def update_device_mac(hass: HomeAssistant, device_id: str, mac: str) -> dict:
    dev_reg = dr.async_get(hass)
    connections = {(CONNECTION_NETWORK_MAC, dr.format_mac(mac))}
    device = dev_reg.async_update_device(device_id, merge_connections=connections)
    return {"result": "update", "device": device.dict_repr}


KNOWN_CONNECTIONS = {CONNECTION_BLUETOOTH, CONNECTION_NETWORK_MAC, CONNECTION_ZIGBEE}


def update_device(
    hass: HomeAssistant, device_id: str, primary_domains: list[str]
) -> dict | None:
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if device.via_device_id:
        return {"result": "skip", "reason": "child device"}

    domains = set(i[0] for i in device.identifiers)

    if any(i[0] in KNOWN_CONNECTIONS for i in device.connections):
        return {"result": "skip", "reason": "already has mac"}

    if "cast" in domains:
        address = get_cast_mac(hass, device)
    elif "yandex_station" in domains:
        address = get_yandex_station_mac(hass, device)
    else:
        address = get_config_entry_mac(hass, device)

    if not address:
        return {"result": "skip", "reason": "can't find host"}

    host, mac = address
    if not mac:
        return {"result": "skip", "reason": f"can't find mac for {host}"}

    connections = {(CONNECTION_NETWORK_MAC, mac)}
    if collision := dev_reg.async_get_device(connections=connections):
        result = "collision"
        collision_domains = set(i[0] for i in collision.identifiers)

        if primary_domains:
            if any(i in primary_domains for i in collision_domains):
                merge_devices(hass, collision, device)
                result = "merge"
            elif any(i in primary_domains for i in domains):
                merge_devices(hass, device, collision)
                result = "merge"

        return {
            "result": result,
            "devices": [
                {
                    "id": device.id,
                    "name": device.name_by_user or device.name,
                    "domains": domains,
                },
                {
                    "id": collision.id,
                    "name": collision.name_by_user or collision.name,
                    "domains": collision_domains,
                },
            ],
            "device": {"host": host, "mac": mac},
        }
    else:
        dev_reg.async_update_device(device.id, merge_connections=connections)
        return {
            "result": "update",
            "device": {
                "id": device.id,
                "name": device.name_by_user or device.name,
                "domains": domains,
                "host": host,
                "mac": mac,
            },
        }


def update_devices(hass: HomeAssistant, primary_domains: list[str]) -> dict:
    results = []

    dev_reg = dr.async_get(hass)
    for device in list(dev_reg.devices.values()):
        item = update_device(hass, device.id, primary_domains)
        if item["result"] == "skip":
            continue
        results.append(item)

    return {"results": results, "arp": ARP.cache}


def get_title(hass: HomeAssistant, host: str, mac: str) -> str | None:
    if host and not mac:
        mac = ARP.get_mac(host)
    if not mac:
        return None

    dev_reg = dr.async_get(hass)
    connections = {(CONNECTION_NETWORK_MAC, mac)}
    primary = dev_reg.async_get_device(connections=connections)
    return (primary.name_by_user or primary.name) if primary else None
