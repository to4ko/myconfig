from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity


class DynamicPeerEntityManager:
    """Manage dynamic peer entities for a platform from coordinator data."""

    def __init__(
        self,
        *,
        coordinator,
        async_add_entities: Callable[[list[CoordinatorEntity]], None],
        create_entities: Callable[[dict[str, Any]], list[CoordinatorEntity]],
    ) -> None:
        self.coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._create_entities = create_entities
        self._entities_by_key: dict[str, list[CoordinatorEntity]] = {}

    def build_initial_entities(self) -> list[CoordinatorEntity]:
        entities: list[CoordinatorEntity] = []
        for client in self.coordinator.data.get("clients", []):
            client_key = client["publicKey"]
            client_entities = self._create_entities(client)
            self._entities_by_key[client_key] = client_entities
            entities.extend(client_entities)
        return entities

    def handle_coordinator_update(self) -> None:
        current_keys = set(self._entities_by_key)
        new_clients = {
            client["publicKey"]: client
            for client in self.coordinator.data.get("clients", [])
        }
        new_keys = set(new_clients)

        new_entities: list[CoordinatorEntity] = []

        for client_key in new_keys - current_keys:
            client_entities = self._create_entities(new_clients[client_key])
            self._entities_by_key[client_key] = client_entities
            new_entities.extend(client_entities)

        for client_key in current_keys - new_keys:
            for entity in self._entities_by_key.pop(client_key):
                entity.async_remove()

        if new_entities:
            self._async_add_entities(new_entities)
