from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfInformation
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import WGEasyConfigEntry
from .const import DOMAIN, ENTITY_ID_PREFIX, SERVER_DEVICE_ID
from .entity_manager import DynamicPeerEntityManager


async def async_setup_entry(hass, entry: WGEasyConfigEntry, async_add_entities):
    coordinator = entry.runtime_data

    manager = DynamicPeerEntityManager(
        coordinator=coordinator,
        async_add_entities=async_add_entities,
        create_entities=lambda client: create_peer_sensor_entities(coordinator, client),
    )

    initial_entities = [
        WGSummarySensor(coordinator, "configured"),
        WGSummarySensor(coordinator, "enabled"),
        WGSummarySensor(coordinator, "connected"),
        *manager.build_initial_entities(),
    ]

    async_add_entities(initial_entities)
    entry.async_on_unload(coordinator.async_add_listener(manager.handle_coordinator_update))


class WGBasePeerEntity(CoordinatorEntity):
    def __init__(self, coordinator, client):
        super().__init__(coordinator)
        self.client_key = client["publicKey"]
        self.client_name_slug = slugify(client.get("name") or self.client_key[:8])
        self._attr_has_entity_name = True
        self._last_pushed_state: tuple[Any, bool] | None = None

    def _get_client(self):
        return self.coordinator.peer_map.get(self.client_key)

    @property
    def available(self) -> bool:
        return self._get_client() is not None and self.coordinator.last_update_success

    @property
    def device_info(self):
        client = self._get_client()
        name = client["name"] if client else self.client_key[:8]
        return DeviceInfo(
            identifiers={(DOMAIN, self.client_key)},
            name=name,
            manufacturer="WireGuard",
            model="Peer",
        )

    def _set_entity_id(self, platform: str, suffix: str) -> None:
        self.entity_id = f"{platform}.{ENTITY_ID_PREFIX}_{self.client_name_slug}_{suffix}"

    def async_write_ha_state(self) -> None:
        current_state = (getattr(self, "native_value", None), self.available)
        if self._last_pushed_state is not None and current_state == self._last_pushed_state:
            return
        self._last_pushed_state = current_state
        super().async_write_ha_state()


class WGSummarySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, sensor_type):
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._attr_has_entity_name = True
        self._attr_name = sensor_type
        self._attr_unique_id = f"wg_server_{sensor_type}"
        self.entity_id = f"sensor.{ENTITY_ID_PREFIX}_server_{sensor_type}"
        self._last_pushed_state: tuple[Any, bool] | None = None

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, SERVER_DEVICE_ID)},
            name="WireGuard server",
            manufacturer="WireGuard",
            model="Server",
        )

    @property
    def native_value(self):
        data = self.coordinator.data

        if self.sensor_type == "configured":
            return data.get("wireguard_configured_peers")
        if self.sensor_type == "enabled":
            return data.get("wireguard_enabled_peers")
        if self.sensor_type == "connected":
            return data.get("wireguard_connected_peers")
        return None

    def async_write_ha_state(self) -> None:
        current_state = (self.native_value, self.available)
        if self._last_pushed_state is not None and current_state == self._last_pushed_state:
            return
        self._last_pushed_state = current_state
        super().async_write_ha_state()


class WGPeerTotalTrafficSensor(WGBasePeerEntity, SensorEntity):
    def __init__(self, coordinator, client, kind):
        super().__init__(coordinator, client)
        self.kind = kind
        self._attr_name = kind
        self._attr_unique_id = f"wg_{self.client_key}_{kind}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
        self._attr_suggested_unit_of_measurement = "MB"
        self._set_entity_id("sensor", kind)

    @property
    def native_value(self):
        client = self._get_client()
        if not client:
            return None

        if self.kind == "rx":
            return client["transferRx"]
        return client["transferTx"]


class WGPeerRateSensor(WGBasePeerEntity, SensorEntity):
    def __init__(self, coordinator, client, kind):
        super().__init__(coordinator, client)
        self.kind = kind
        self._attr_name = kind
        self._attr_unique_id = f"wg_{self.client_key}_{kind}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = SensorDeviceClass.DATA_RATE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
        self._attr_suggested_unit_of_measurement = "kB/s"
        self._set_entity_id("sensor", kind)

    @property
    def native_value(self):
        client = self._get_client()
        if not client:
            return None

        if self.kind == "rx_rate":
            return client.get("transferRxRate")
        return client.get("transferTxRate")


class WGPeerTextSensor(WGBasePeerEntity, SensorEntity):
    def __init__(self, coordinator, client, kind, sensor_name=None):
        super().__init__(coordinator, client)
        self.kind = kind
        self._attr_name = sensor_name or kind
        self._attr_unique_id = f"wg_{self.client_key}_{kind}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._set_entity_id("sensor", slugify(kind))
        # wg-easy v14 never provides "endpoint" or "ipv6Address" (v14 has no
        # IPv6 client concept, and doesn't surface the live endpoint from
        # `wg show` via its API at all - confirmed against v14's source).
        # Rather than hard-coding that per API version, disable the entity
        # by default whenever the value is missing at creation time - this
        # naturally keeps ipv4Address enabled (always present on both
        # versions for a real client) while endpoint/ipv6Address start out
        # disabled on v14 servers, without sensor.py needing to know which
        # API version produced the data. Users can still enable them by
        # hand if a value shows up later.
        self._attr_entity_registry_enabled_default = client.get(kind) is not None

    @property
    def native_value(self):
        client = self._get_client()
        if not client:
            return None

        return client.get(self.kind)


class WGPeerHandshakeSensor(WGBasePeerEntity, SensorEntity):
    def __init__(self, coordinator, client):
        super().__init__(coordinator, client)
        self._attr_name = "last handshake"
        self._attr_unique_id = f"wg_{self.client_key}_handshake"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._set_entity_id("sensor", "last_handshake")

    @property
    def native_value(self):
        client = self._get_client()
        if not client or not client["latestHandshakeAt"]:
            return None

        return datetime.fromisoformat(client["latestHandshakeAt"].replace("Z", "+00:00"))


def create_peer_sensor_entities(coordinator, client):
    return [
        WGPeerTotalTrafficSensor(coordinator, client, "rx"),
        WGPeerTotalTrafficSensor(coordinator, client, "tx"),
        WGPeerRateSensor(coordinator, client, "rx_rate"),
        WGPeerRateSensor(coordinator, client, "tx_rate"),
        WGPeerTextSensor(coordinator, client, "endpoint"),
        WGPeerTextSensor(coordinator, client, "ipv4Address", "ipv4 address"),
        WGPeerTextSensor(coordinator, client, "ipv6Address", "ipv6 address"),
        WGPeerHandshakeSensor(coordinator, client),
    ]
