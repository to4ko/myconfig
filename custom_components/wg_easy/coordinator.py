from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WGEasyApiError, WGEasyAuthError, WGEasyV14Client, WGEasyV15Client
from .const import API_VERSION_V14, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class WGEasyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass,
        *,
        config_entry_id: str,
        url: str,
        api_version: str,
        token: str | None = None,
        password: str | None = None,
        verify_ssl: bool = True,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(5, int(poll_interval))),
        )
        self.url = url
        self.api_version = api_version
        self.config_entry_id = config_entry_id
        self.session = async_get_clientsession(hass)

        self._client: WGEasyV14Client | WGEasyV15Client
        if api_version == API_VERSION_V14:
            self._client = WGEasyV14Client(self.session, url, password, verify_ssl)
        else:
            self._client = WGEasyV15Client(self.session, url, token, verify_ssl)

        self._known_client_keys: set[str] = set()
        self.peer_map: dict[str, dict[str, Any]] = {}
        self._previous_counters: dict[str, tuple[datetime, int, int]] = {}
        self._last_raw_response: bytes | None = None
        self._last_normalized_data: dict[str, Any] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            raw_body = await self._client.async_fetch_raw()
        except WGEasyAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except WGEasyApiError as err:
            raise UpdateFailed(str(err)) from err

        if raw_body == self._last_raw_response and self._last_normalized_data is not None:
            # The server returned byte-for-byte the same payload as last poll.
            # Skip the JSON decode + per-peer normalization pass entirely, but
            # keep the rate-limiting bookkeeping fresh so that a later real
            # change doesn't produce an artificially inflated transfer rate.
            now = dt_util.utcnow()
            self._previous_counters = {
                client_key: (now, rx, tx)
                for client_key, (_, rx, tx) in self._previous_counters.items()
            }
            return self._last_normalized_data

        try:
            payload = json.loads(raw_body)
        except ValueError as err:
            raise UpdateFailed(f"Invalid JSON response: {err}") from err

        data = self._normalize_payload(payload)
        self.peer_map = {client["publicKey"]: client for client in data["clients"]}
        self._remove_stale_devices(set(self.peer_map))

        self._last_raw_response = raw_body
        self._last_normalized_data = data
        return data

    def _normalize_payload(self, payload: Any) -> dict[str, Any]:
        """Normalize a v14 or v15 payload into a common shape.

        v15 returns a dict with a "clients" list, each keyed by "publicKey",
        with dedicated "ipv4Address"/"ipv6Address" fields (see wg-easy's
        clients_table schema). v14 returns a bare list, each keyed by "id",
        with a single "address" field (IPv4 only - v14 has no IPv6 client
        address concept at all) and no "ipv4Address"/"ipv6Address" keys.
        Both are normalized here to use "publicKey" as the canonical
        identifier and "ipv4Address"/"ipv6Address" as the canonical address
        fields, so sensor.py / binary_sensor.py / entity_manager.py don't
        need to know which API version produced the data.
        """
        if isinstance(payload, list):
            clients = payload
            base_payload: dict[str, Any] = {}
        elif isinstance(payload, dict):
            clients = payload.get("clients") or []
            base_payload = payload
        else:
            clients = []
            base_payload = {}

        now = dt_util.utcnow()

        normalized_clients: list[dict[str, Any]] = []
        next_previous_counters: dict[str, tuple[datetime, int, int]] = {}

        for client in clients:
            public_key = client.get("publicKey") or client.get("id")
            if not public_key:
                continue

            transfer_rx = int(client.get("transferRx") or 0)
            transfer_tx = int(client.get("transferTx") or 0)
            transfer_rx_rate = 0.0
            transfer_tx_rate = 0.0

            previous = self._previous_counters.get(public_key)
            if previous is not None:
                previous_time, previous_rx, previous_tx = previous
                elapsed = (now - previous_time).total_seconds()
                if elapsed > 0:
                    rx_delta = transfer_rx - previous_rx
                    tx_delta = transfer_tx - previous_tx
                    transfer_rx_rate = max(0.0, rx_delta / elapsed)
                    transfer_tx_rate = max(0.0, tx_delta / elapsed)

            next_previous_counters[public_key] = (now, transfer_rx, transfer_tx)

            # v15 exposes dedicated ipv4Address/ipv6Address fields. v14 only
            # exposes a single "address" field (its client model is IPv4-only
            # and has no "ipv4Address"/"ipv6Address" keys at all). Fall back
            # to allowedIps as a last resort for any future/other shape.
            allowed_ips = client.get("allowedIps") or []
            inferred_ipv4 = (
                allowed_ips[0] if isinstance(allowed_ips, list) and allowed_ips else None
            )
            ipv4_address = (
                client.get("ipv4Address") or client.get("address") or inferred_ipv4
            )

            normalized_clients.append(
                {
                    **client,
                    "publicKey": public_key,
                    "name": client.get("name") or public_key[:8],
                    "transferRx": transfer_rx,
                    "transferTx": transfer_tx,
                    "transferRxRate": round(transfer_rx_rate, 2),
                    "transferTxRate": round(transfer_tx_rate, 2),
                    "endpoint": client.get("endpoint") or None,
                    "ipv4Address": ipv4_address,
                    "ipv6Address": client.get("ipv6Address") or None,
                    "enabled": bool(client.get("enabled", False)),
                    "latestHandshakeAt": client.get("latestHandshakeAt") or None,
                }
            )

        self._previous_counters = next_previous_counters

        return {
            **base_payload,
            "clients": normalized_clients,
            "wireguard_configured_peers": base_payload.get(
                "wireguard_configured_peers", len(normalized_clients)
            ),
            "wireguard_enabled_peers": base_payload.get(
                "wireguard_enabled_peers",
                sum(1 for client in normalized_clients if client["enabled"]),
            ),
            "wireguard_connected_peers": base_payload.get(
                "wireguard_connected_peers",
                sum(
                    1
                    for client in normalized_clients
                    if client["latestHandshakeAt"] is not None
                ),
            ),
        }

    def _remove_stale_devices(self, current_client_keys: set[str]) -> None:
        stale_client_keys = self._known_client_keys - current_client_keys
        if not stale_client_keys:
            self._known_client_keys = current_client_keys
            return

        device_registry = dr.async_get(self.hass)

        for client_key in stale_client_keys:
            device = device_registry.async_get_device(identifiers={(DOMAIN, client_key)})
            if device is not None:
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry_id,
                )
            self._previous_counters.pop(client_key, None)

        self._known_client_keys = current_client_keys
