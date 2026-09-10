from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import WGEasyConfigEntry
from .const import DEFAULT_ONLINE_TIMEOUT_SECONDS, DOMAIN, ENTITY_ID_PREFIX
from .entity_manager import DynamicPeerEntityManager


async def async_setup_entry(hass, entry: WGEasyConfigEntry, async_add_entities):
    coordinator = entry.runtime_data

    manager = DynamicPeerEntityManager(
        coordinator=coordinator,
        async_add_entities=async_add_entities,
        create_entities=lambda client: create_peer_binary_entities(coordinator, client, entry),
    )

    initial_entities = manager.build_initial_entities()
    if initial_entities:
        async_add_entities(initial_entities)

    entry.async_on_unload(coordinator.async_add_listener(manager.handle_coordinator_update))


class WGPeerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, client, sensor_type, entry):
        super().__init__(coordinator)

        self.client_key = client["publicKey"]
        self.client_name_slug = slugify(client.get("name") or self.client_key[:8])
        self.sensor_type = sensor_type
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_name = sensor_type
        self._attr_unique_id = f"wg_{self.client_key}_{sensor_type}"
        self.entity_id = f"binary_sensor.{ENTITY_ID_PREFIX}_{self.client_name_slug}_{sensor_type}"
        self._last_pushed_state: tuple[Any, bool] | None = None

    def _get_client(self):
        return self.coordinator.peer_map.get(self.client_key)

    @property
    def _online_timeout_seconds(self) -> int:
        return self._entry.options.get(
            "online_timeout_seconds", DEFAULT_ONLINE_TIMEOUT_SECONDS
        )

    @property
    def is_on(self):
        client = self._get_client()
        if not client:
            return False

        if self.sensor_type == "online":
            handshake = client.get("latestHandshakeAt")
            if not handshake:
                return False

            try:
                handshake_dt = datetime.fromisoformat(handshake.replace("Z", "+00:00"))
            except ValueError:
                return False

            timeout = timedelta(seconds=self._online_timeout_seconds)
            return datetime.now(UTC) - handshake_dt <= timeout

        if self.sensor_type == "enabled":
            return client["enabled"]

        return False

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

    def async_write_ha_state(self) -> None:
        """Skip redundant state writes to Home Assistant when nothing changed."""
        current_state = (self.is_on, self.available)
        if self._last_pushed_state is not None and current_state == self._last_pushed_state:
            return
        self._last_pushed_state = current_state
        super().async_write_ha_state()


def create_peer_binary_entities(coordinator, client, entry):
    return [
        WGPeerBinarySensor(coordinator, client, "online", entry),
        WGPeerBinarySensor(coordinator, client, "enabled", entry),
    ]
