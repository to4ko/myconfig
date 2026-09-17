"""WebSocket-команды панели «Яндекс меню»."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import sys
import time
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    CACHE_TTL,
    CONDITIONAL_DOMAINS,
    DATA_API,
    DATA_CACHE,
    DATA_SNAPSHOTS,
    DATA_STORE,
    DOMAIN,
    EXPOSABLE_DOMAINS,
    MAX_NAMES,
    YAHA_DOMAIN,
)
from .quasar_api import QuasarApi, QuasarError

_LOGGER = logging.getLogger(__name__)

PARALLEL_CONFIG_REQUESTS = 6


# --------------------------------------------------------------------- helpers


def _api(hass: HomeAssistant) -> QuasarApi:
    return hass.data[DOMAIN][DATA_API]


def _label_info(hass: HomeAssistant) -> dict[str, Any]:
    """Как Yaha решает, что отдавать в Алису: метка или ручной список."""
    for entry in hass.config_entries.async_entries(YAHA_DOMAIN):
        options = entry.options or {}
        source = options.get("filter_source")
        label = options.get("label")
        if source == "label" and label:
            return {"supported": True, "label_id": label, "reason": None}
        return {
            "supported": False,
            "label_id": None,
            "reason": (
                "В интеграции Yandex Smart Home выбран не режим меток, а ручной "
                "список сущностей — добавлять устройства отсюда нельзя."
            ),
        }
    return {
        "supported": False,
        "label_id": None,
        "reason": "Интеграция Yandex Smart Home не настроена.",
    }


def _is_ha_entity(hass: HomeAssistant, external_id: str | None) -> bool:
    """Устройство создано нашим навыком из сущности HA?"""
    if not external_id or "." not in external_id:
        return False
    if hass.states.get(external_id) is not None:
        return True
    return er.async_get(hass).async_get(external_id) is not None


def _remember(
    snapshots: dict[str, Any], key: str, device: dict[str, Any], force: bool = False
) -> None:
    """Обновляем слепок, но не затираем его обеднённым состоянием.

    После пересоздания устройства в Яндексе у него остаётся одно имя и роль
    по умолчанию — именно это и надо уметь откатить, поэтому такой слепок
    молча не перезаписываем.
    """
    fresh = _snapshot_of(device)
    old = snapshots.get(key)
    if force or not old or len(fresh["names"]) >= len(old.get("names") or []):
        snapshots[key] = fresh


def _on_state(device: dict[str, Any]) -> bool | None:
    """Включено ли устройство по данным Яндекса. None — у него нет вкл/выкл."""
    for capability in device.get("capabilities") or []:
        if capability.get("type") == "devices.capabilities.on_off":
            value = (capability.get("state") or {}).get("value")
            return value if isinstance(value, bool) else None
    return None


def _snapshot_of(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "names": list(device.get("names") or []),
        "room": device.get("room"),
        "role": device.get("role"),
        "saved_at": time.time(),
    }


async def _collect(hass: HomeAssistant, use_cache: bool = True) -> dict[str, Any]:
    """Собирает всё, что нужно панели, за один заход."""
    store_data = hass.data[DOMAIN]
    cache = store_data.get(DATA_CACHE)
    if use_cache and cache and time.time() - cache["ts"] < CACHE_TTL:
        return cache["payload"]

    api = _api(hass)
    raw = await api.devices()

    flat: list[tuple[dict[str, Any], str | None, str | None]] = []
    for room in raw.get("rooms") or []:
        for device in room.get("devices") or []:
            flat.append((device, room.get("name"), room.get("id")))
    for device in raw.get("unconfigured_devices") or []:
        flat.append((device, None, None))

    semaphore = asyncio.Semaphore(PARALLEL_CONFIG_REQUESTS)

    async def load(device: dict[str, Any]) -> dict[str, Any] | None:
        async with semaphore:
            try:
                return await api.device_config(device["id"])
            except QuasarError as err:
                _LOGGER.debug("Карточка %s не прочиталась: %s", device["id"], err)
                return None

    configs = await asyncio.gather(*(load(item[0]) for item in flat))

    snapshots: dict[str, Any] = hass.data[DOMAIN][DATA_SNAPSHOTS]
    devices: list[dict[str, Any]] = []
    skill_id: str | None = None

    for (device, room_name, room_id), config in zip(flat, configs, strict=True):
        config = config or {}
        device_type = config.get("device_type") or {}
        external_id = config.get("external_id")
        from_ha = _is_ha_entity(hass, external_id)
        entry: dict[str, Any] = {
            "id": device["id"],
            "name": config.get("name") or device.get("name"),
            "names": config.get("names") or [device.get("name")],
            "type": device.get("type"),
            "current_type": device_type.get("current_type") or device.get("type"),
            "role": device_type.get("role"),
            "role_switchable": bool(device_type.get("role_switchable")),
            "type_switchable": bool(device_type.get("switchable")),
            "room": room_name,
            "room_id": room_id,
            "external_id": external_id,
            "from_ha": from_ha,
            "skill_id": config.get("skill_id"),
            "switchable": any(
                capability.get("type") == "devices.capabilities.on_off"
                for capability in (device.get("capabilities") or [])
            ),
            "on": _on_state(device),
        }
        if from_ha:
            entry["ha_state"] = hass.states.get(external_id) is not None
            _remember(snapshots, external_id, entry)
            if not skill_id and config.get("skill_id"):
                skill_id = config["skill_id"]
        devices.append(entry)

    hass.data[DOMAIN][DATA_STORE].async_delay_save(lambda: snapshots, 5)

    label = _label_info(hass)
    exposed = {
        device["external_id"] for device in devices if device.get("external_id")
    }
    unexposed = _unexposed_entities(hass, exposed)

    payload = {
        "devices": devices,
        "rooms": [
            {"id": room.get("id"), "name": room.get("name")}
            for room in (raw.get("rooms") or [])
        ],
        "unexposed": unexposed,
        "label": label,
        "snapshots": snapshots,
        "max_names": MAX_NAMES,
        "skill_id": skill_id,
    }
    hass.data[DOMAIN][DATA_CACHE] = {"ts": time.time(), "payload": payload}
    return payload


def _yaha_can_export(hass: HomeAssistant) -> Callable[[str, State | None], bool]:
    """Проверка «уйдёт ли сущность в Алису» по правилам самого Yandex Smart Home.

    Если его внутренности недоступны (другая версия), проверяем грубо:
    у датчика должен быть класс, иначе Яндекс не поймёт, что он измеряет.
    """

    def by_device_class(_entity_id: str, state: State | None) -> bool:
        return bool(state and state.attributes.get("device_class"))

    module = sys.modules.get(f"custom_components.{YAHA_DOMAIN}.device")
    component = hass.data.get(YAHA_DOMAIN)
    entries = hass.config_entries.async_entries(YAHA_DOMAIN)
    if module is None or component is None or not entries:
        return by_device_class
    try:
        entry_data = component.get_entry_data(entries[0])
        yaha_device = module.Device
    except Exception:  # noqa: BLE001 — устройство Yandex Smart Home поменялось
        return by_device_class

    def by_yaha(entity_id: str, state: State | None) -> bool:
        try:
            device = yaha_device(hass, entry_data, entity_id, state)
            return bool(device.get_capabilities() or device.get_properties())
        except Exception:  # noqa: BLE001
            return by_device_class(entity_id, state)

    return by_yaha


def _unexposed_entities(
    hass: HomeAssistant, exposed: set[str]
) -> list[dict[str, Any]]:
    """Сущности HA, которых в Алисе ещё нет."""
    registry = er.async_get(hass)
    areas = ar.async_get(hass)
    devices = dr.async_get(hass)
    can_export = _yaha_can_export(hass)
    result: list[dict[str, Any]] = []
    for entity in registry.entities.values():
        if entity.domain not in EXPOSABLE_DOMAINS:
            continue
        if entity.disabled_by or entity.hidden_by or entity.entity_category:
            continue
        if entity.entity_id in exposed:
            continue
        state = hass.states.get(entity.entity_id)
        if entity.domain in CONDITIONAL_DOMAINS and not can_export(entity.entity_id, state):
            continue
        area_id = entity.area_id
        if not area_id and entity.device_id:
            device_entry = devices.async_get(entity.device_id)
            area_id = device_entry.area_id if device_entry else None
        area = areas.async_get_area(area_id) if area_id else None
        result.append(
            {
                "entity_id": entity.entity_id,
                "name": (
                    entity.name
                    or (state.attributes.get("friendly_name") if state else None)
                    or entity.original_name
                    or entity.entity_id
                ),
                "area": area.name if area else None,
                "available": bool(state)
                and state.state not in ("unavailable", "unknown"),
            }
        )
    result.sort(key=lambda item: (item["area"] or "яя", item["name"]))
    return result


def _drop_cache(hass: HomeAssistant) -> None:
    hass.data[DOMAIN][DATA_CACHE] = None


async def _reply(hass, connection, msg, coro, remember: str | None = None) -> None:
    """Выполняет действие и отвечает свежим списком.

    Если действие вернуло строку — она уедет в панель как примечание.
    `remember` — id устройства, чей слепок надо освежить принудительно.
    """
    notice: str | None = None
    try:
        result = await coro
        if isinstance(result, str):
            notice = result
    except QuasarError as err:
        connection.send_error(msg["id"], "quasar_error", str(err))
        return
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Неожиданная ошибка команды панели")
        connection.send_error(msg["id"], "unknown_error", str(err))
        return
    _drop_cache(hass)
    try:
        payload = await _collect(hass, use_cache=False)
    except QuasarError as err:
        connection.send_error(msg["id"], "quasar_error", str(err))
        return
    if remember:
        snapshots = hass.data[DOMAIN][DATA_SNAPSHOTS]
        for device in payload["devices"]:
            if device["id"] == remember and device.get("external_id"):
                _remember(snapshots, device["external_id"], device, force=True)
                hass.data[DOMAIN][DATA_STORE].async_delay_save(lambda: snapshots, 2)
                break
    payload = {**payload, "notice": notice}
    connection.send_result(msg["id"], payload)


# -------------------------------------------------------------------- commands


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/list",
        vol.Optional("force", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_list(hass: HomeAssistant, connection, msg) -> None:
    try:
        payload = await _collect(hass, use_cache=not msg["force"])
    except QuasarError as err:
        connection.send_error(msg["id"], "quasar_error", str(err))
        return
    connection.send_result(msg["id"], payload)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/name_add",
        vol.Required("device_id"): str,
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=64)),
    }
)
@websocket_api.async_response
async def ws_name_add(hass: HomeAssistant, connection, msg) -> None:
    await _reply(
        hass,
        connection,
        msg,
        _api(hass).add_name(msg["device_id"], msg["name"].strip()),
        remember=msg["device_id"],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/name_delete",
        vol.Required("device_id"): str,
        vol.Required("name"): str,
    }
)
@websocket_api.async_response
async def ws_name_delete(hass: HomeAssistant, connection, msg) -> None:
    await _reply(
        hass,
        connection,
        msg,
        _api(hass).delete_name(msg["device_id"], msg["name"]),
        remember=msg["device_id"],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/name_primary",
        vol.Required("device_id"): str,
        vol.Required("name"): str,
    }
)
@websocket_api.async_response
async def ws_name_primary(hass: HomeAssistant, connection, msg) -> None:
    await _reply(
        hass,
        connection,
        msg,
        _api(hass).make_primary(msg["device_id"], msg["name"]),
        remember=msg["device_id"],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/set_room",
        vol.Required("device_id"): str,
        vol.Required("room_id"): str,
    }
)
@websocket_api.async_response
async def ws_set_room(hass: HomeAssistant, connection, msg) -> None:
    await _reply(
        hass, connection, msg, _api(hass).set_room(msg["device_id"], msg["room_id"])
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/set_role",
        vol.Required("device_id"): str,
        vol.Required("role"): vol.In(["main", "secondary"]),
    }
)
@websocket_api.async_response
async def ws_set_role(hass: HomeAssistant, connection, msg) -> None:
    async def run() -> None:
        api = _api(hass)
        config = await api.device_config(msg["device_id"])
        device_type = (config.get("device_type") or {}).get("current_type")
        if not device_type:
            raise QuasarError("Не удалось определить тип устройства.")
        await api.set_type(
            msg["device_id"], device_type, f"devices.roles.light.{msg['role']}"
        )

    await _reply(hass, connection, msg, run(), remember=msg["device_id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/delete_device",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_device(hass: HomeAssistant, connection, msg) -> None:
    await _reply(hass, connection, msg, _api(hass).delete_device(msg["device_id"]))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/discovery",
        vol.Optional("skill_id"): str,
    }
)
@websocket_api.async_response
async def ws_discovery(hass: HomeAssistant, connection, msg) -> None:
    async def run() -> None:
        skill_id = msg.get("skill_id")
        if not skill_id:
            payload = await _collect(hass, use_cache=True)
            skill_id = payload.get("skill_id")
        if not skill_id:
            raise QuasarError(
                "Не нашёл навык Home Assistant в Яндекс-доме — "
                "отдайте в Алису хотя бы одну сущность."
            )
        await _api(hass).discovery(skill_id)

    await _reply(hass, connection, msg, run())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/expose",
        vol.Required("entity_id"): str,
        vol.Required("expose"): bool,
    }
)
@websocket_api.async_response
async def ws_expose(hass: HomeAssistant, connection, msg) -> None:
    async def run() -> str | None:
        label = _label_info(hass)
        if not label["supported"]:
            raise QuasarError(label["reason"])
        registry = er.async_get(hass)
        entity = registry.async_get(msg["entity_id"])
        if not entity:
            raise QuasarError(f"Сущности {msg['entity_id']} нет в реестре.")

        # В реестре встречается мусорный псевдоним [null]: Yaha берёт его как
        # имя и Яндекс заводит устройство под названием «0». Чистим до выдачи.
        if msg["expose"]:
            clean = {
                alias
                for alias in (entity.aliases or set())
                if isinstance(alias, str) and alias.strip()
            }
            if clean != set(entity.aliases or set()):
                registry.async_update_entity(msg["entity_id"], aliases=clean)
                entity = registry.async_get(msg["entity_id"])
                _LOGGER.debug(
                    "Почистил псевдонимы %s: теперь %s",
                    msg["entity_id"],
                    entity.aliases,
                )

        labels = set(entity.labels)
        if msg["expose"]:
            labels.add(label["label_id"])
        else:
            labels.discard(label["label_id"])
        registry.async_update_entity(msg["entity_id"], labels=labels)
        payload = await _collect(hass, use_cache=True)
        if payload.get("skill_id"):
            await _api(hass).discovery(payload["skill_id"])

        if not msg["expose"]:
            return "Метка снята. Устройство останется в Яндексе, пока его не удалить."

        state = hass.states.get(msg["entity_id"])
        if state is None or state.state in ("unavailable", "unknown"):
            return (
                "Сущность сейчас недоступна, Яндекс такие не принимает. "
                "Метку поставил — устройство появится, когда сущность оживёт "
                "и вы нажмёте «Обновить список»."
            )
        return "Отдал в Алису. Устройство появится в течение минуты."

    await _reply(hass, connection, msg, run())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/withdraw",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_withdraw(hass: HomeAssistant, connection, msg) -> None:
    """Убрать из Алисы совсем: снять метку и удалить устройство в Яндексе."""

    async def run() -> str | None:
        api = _api(hass)
        config = await api.device_config(msg["device_id"])
        entity_id = config.get("external_id")
        label = _label_info(hass)
        if entity_id and label["supported"]:
            registry = er.async_get(hass)
            entity = registry.async_get(entity_id)
            if entity and label["label_id"] in entity.labels:
                registry.async_update_entity(
                    entity_id, labels=set(entity.labels) - {label["label_id"]}
                )
        await api.delete_device(msg["device_id"])
        return "Убрал из Алисы: снял метку и удалил устройство."

    await _reply(hass, connection, msg, run())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/blink",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_blink(hass: HomeAssistant, connection, msg) -> None:
    try:
        hass.async_create_task(_api(hass).blink(msg["device_id"]))
    except QuasarError as err:
        connection.send_error(msg["id"], "quasar_error", str(err))
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "yandex_menu/restore",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_restore(hass: HomeAssistant, connection, msg) -> None:
    async def run() -> None:
        api = _api(hass)
        config = await api.device_config(msg["device_id"])
        external_id = config.get("external_id")
        snapshot = hass.data[DOMAIN][DATA_SNAPSHOTS].get(external_id)
        if not snapshot:
            raise QuasarError("Для этого устройства нет сохранённого слепка.")

        current = list(config.get("names") or [])
        wanted = [name for name in snapshot.get("names") or [] if name]
        if not wanted:
            raise QuasarError("В слепке нет имён.")

        for name in wanted:
            if name not in current:
                await api.add_name(msg["device_id"], name)
        for name in current:
            if name not in wanted:
                await api.delete_name(msg["device_id"], name)
        await api.make_primary(msg["device_id"], wanted[0])

        role = snapshot.get("role")
        device_type = (config.get("device_type") or {}).get("current_type")
        if role and device_type:
            await api.set_type(msg["device_id"], device_type, role)

    await _reply(hass, connection, msg, run())


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (
        ws_list,
        ws_name_add,
        ws_name_delete,
        ws_name_primary,
        ws_set_room,
        ws_set_role,
        ws_delete_device,
        ws_discovery,
        ws_expose,
        ws_withdraw,
        ws_blink,
        ws_restore,
    ):
        websocket_api.async_register_command(hass, command)
