"""WebSocket-команды панели «Яндекс меню»."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import itertools
import logging
import re
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

from .accounts import (
    account_key,
    station_entries,
    station_entry,
    yaha_entries,
    yaha_entry,
)
from .const import (
    CACHE_TTL,
    CONDITIONAL_DOMAINS,
    DATA_API,
    DATA_BUILD,
    DATA_BUILDS,
    DATA_CACHE,
    DATA_CACHE_OWNER,
    DATA_CACHE_STORE,
    DATA_CONFIGS,
    DATA_DETAILS,
    DATA_PROGRESS,
    DATA_PROGRESS_LISTENERS,
    DATA_SAVED,
    DATA_SAVED_STORE,
    DATA_SAVED_TURN,
    DATA_SNAPSHOTS,
    DATA_STALE,
    DATA_STORE,
    DATA_STORE_DATA,
    DOMAIN,
    EXPOSABLE_DOMAINS,
    MAX_NAMES,
    YAHA_DOMAIN,
    YS_DOMAIN,
)
from .quasar_api import QuasarApi, QuasarError

_LOGGER = logging.getLogger(__name__)

PARALLEL_CONFIG_REQUESTS = 6

# Служебные сценарии Яндекс.Станции: через них она шлёт команды из облака
HELPER_SCENARIO = re.compile(r"^ХА [0-9a-f-]{36}$")

# Умения, которыми управляют голосом. quasar.* у колонок — служебные.
VOICE_CAPABILITIES = ("on_off", "color_setting", "range", "mode", "toggle", "video_stream")

# В общем списке у этих умений нет названий значений (цвета, режимы) и бывают
# пропуски, поэтому за ними идём в карточку устройства. Остальным хватает списка.
DETAIL_CAPABILITIES = ("devices.capabilities.color_setting", "devices.capabilities.mode")

# Яндекс.Станция держит паузу 0,2 с между любыми запросами, а настройки и карточку
# Яндекс отдаёт только по одному устройству. В доме на сотни устройств полная
# сборка идёт минутами, поэтому и то и другое кэшируем и храним на диске. Умения
# не меняются почти никогда, настройки — редко: свои правки панель сбрасывает
# сразу, смену основного имени в приложении Яндекса видно по общему списку, а
# «Обновить список» перечитывает всё.
DETAIL_TTL = 7 * 24 * 3600
CONFIG_TTL = 7 * 24 * 3600

# Что из ответов Яндекса нужно панели — только это и кладём на диск
CONFIG_KEYS = ("name", "names", "device_type", "external_id", "skill_id")
DETAIL_KEYS = ("capabilities", "properties")

# Прогресс сборки панели шлём не чаще, чем раз в полсекунды
PROGRESS_EVERY = 0.5
# Прочитанное долгой сборкой кладём на диск раз в минуту (запись идёт через 30 с)
SAVE_EVERY = 60

# Сборки нумеруются по порядку запуска: какой список новее, решаем по номеру,
# а не по часам — часы могут и прыгнуть.
_TURNS = itertools.count(1)

# Устройство Яндекса с тем, где оно стоит: комната (имя, id) и дом
Placed = tuple[dict[str, Any], str | None, str | None, str | None]


# --------------------------------------------------------------------- helpers


def _api(hass: HomeAssistant) -> QuasarApi:
    return hass.data[DOMAIN][DATA_API]


def _label_info(hass: HomeAssistant) -> dict[str, Any]:
    """Как Yaha решает, что отдавать в Алису: метка или ручной список."""
    entry = yaha_entry(hass)
    if entry is None and yaha_entries(hass):
        return {
            "supported": False,
            "label_id": None,
            "reason": (
                "Запись Yandex Smart Home, выбранная в настройках, удалена — выберите "
                "другую: Настройки → Устройства и службы → Яндекс меню → Настроить."
            ),
        }
    if entry is not None:
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


def _skills_of(source: dict[str, Any]) -> dict[str, Any]:
    """Умения устройства в компактном виде: только то, что нужно для фраз.

    Годится и для карточки устройства, и для строки общего списка — но в
    общем списке Яндекс отдаёт умения неполно и без названий значений.
    """
    capabilities: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []
    if "smart_speaker" in (source.get("type") or ""):
        # у колонок служебные умения, голосом ими не управляют
        return {"capabilities": capabilities, "properties": properties}

    for capability in source.get("capabilities") or []:
        kind = (capability.get("type") or "").removeprefix("devices.capabilities.")
        if kind not in VOICE_CAPABILITIES:
            continue
        params = capability.get("parameters") or {}
        item: dict[str, Any] = {
            "kind": kind,
            "instance": params.get("instance"),
            "name": params.get("name"),
        }
        if kind == "color_setting":
            temperature = params.get("temperature_k") or {}
            scenes = params.get("scenes") or (params.get("color_scene") or {}).get("scenes")
            item["color"] = bool(params.get("color_model"))
            item["white"] = temperature.get("min") != temperature.get("max")
            item["palette"] = [
                color["name"] for color in params.get("palette") or [] if color.get("name")
            ]
            item["scenes"] = [
                scene.get("name") or scene.get("id")
                for scene in scenes or []
                if scene.get("name") or scene.get("id")
            ]
        elif kind == "mode":
            item["modes"] = [
                mode.get("name") or mode.get("value")
                for mode in params.get("modes") or []
                if mode.get("name") or mode.get("value")
            ]
        capabilities.append(item)

    for prop in source.get("properties") or []:
        kind = (prop.get("type") or "").removeprefix("devices.properties.")
        if kind not in ("float", "event"):
            continue
        params = prop.get("parameters") or {}
        properties.append(
            {
                "kind": kind,
                "instance": params.get("instance"),
                "name": params.get("name"),
                "events": [
                    event["name"] for event in params.get("events") or [] if event.get("name")
                ],
            }
        )
    return {"capabilities": capabilities, "properties": properties}


def _skills_summary(skills: dict[str, Any]) -> list[str]:
    """Короткий перечень умений для значков в списке."""
    kinds: list[str] = []

    def add(kind: str) -> None:
        if kind not in kinds:
            kinds.append(kind)

    for capability in skills["capabilities"]:
        kind = capability["kind"]
        if kind == "range":
            add(capability.get("instance") or "range")
        elif kind == "color_setting":
            if capability["color"]:
                add("color")
            if capability["white"]:
                add("white")
            if capability["scenes"]:
                add("scenes")
        else:
            add(kind)
    for prop in skills["properties"]:
        add("sensor" if prop["kind"] == "float" else "event")
    return kinds


def _scenarios_of(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Сценарии пользователя и фразы, которыми они запускаются."""
    result = []
    for scenario in raw or []:
        name = scenario.get("name") or ""
        if HELPER_SCENARIO.match(name) or scenario.get("archived"):
            continue
        phrases = [
            trigger["value"]
            for trigger in scenario.get("triggers") or []
            if trigger.get("type") == "scenario.trigger.voice"
            and isinstance(trigger.get("value"), str)
        ]
        result.append(
            {
                "id": scenario.get("id"),
                "name": name,
                "phrases": phrases,
                "active": scenario.get("is_active", True),
                # пустой список — сценарий не привязан к дому, показываем везде
                "households": list(scenario.get("household_ids") or []),
            }
        )
    return result


def _stations(hass: HomeAssistant, flat: list[Placed]) -> list[dict[str, Any]]:
    """Станции, через которые можно проверить фразу, с их домами и комнатами в Яндексе.

    Станция выполняет фразу у себя дома, поэтому панель предлагает только
    станции того дома, который сейчас открыт.
    """
    account = station_entry(hass)
    speakers: dict[str, tuple[str | None, str | None, str | None]] = {}
    for device, room_name, _room_id, household_id in flat:
        quasar_id = (device.get("quasar_info") or {}).get("device_id")
        if quasar_id:
            speakers[quasar_id] = (device.get("name"), room_name, household_id)

    found = []
    for entity in er.async_get(hass).entities.values():
        if entity.platform != YS_DOMAIN or entity.domain != "media_player":
            continue
        if entity.disabled_by:
            continue
        if account and entity.config_entry_id != account.entry_id:
            continue  # Станции другого аккаунта выполнят фразу в чужом доме
        state = hass.states.get(entity.entity_id)
        name, room, household_id = speakers.get(entity.unique_id, (None, None, None))
        found.append(
            {
                "entity_id": entity.entity_id,
                "name": name
                or (state.attributes.get("friendly_name") if state else None)
                or entity.entity_id,
                "room": room,
                "household_id": household_id,
                "speaker": entity.unique_id in speakers,
            }
        )
    # Если сопоставить с колонками Яндекса удалось — остальное (ТВ, модули) не нужно
    if any(item["speaker"] for item in found):
        found = [item for item in found if item["speaker"]]
    found.sort(key=lambda item: item["name"])
    return found


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


def _households_of(
    raw: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Placed]]:
    """Дома, комнаты и устройства из ответа /m/v3/user/devices.

    Комнаты в разных домах могут называться одинаково («Кухня» в квартире и на
    даче), поэтому у каждой комнаты и устройства запоминаем, в каком они доме.
    Группы пропускаем: у них нет карточки устройства, панель с ними не работает.
    """
    households: list[dict[str, Any]] = []
    rooms: list[dict[str, Any]] = []
    flat: list[Placed] = []

    def is_device(item: dict[str, Any]) -> bool:
        return item.get("item_type", "device") == "device" and bool(item.get("id"))

    for house in raw.get("households") or []:
        house_id = house.get("id")
        households.append(
            {
                "id": house_id,
                "name": house.get("name") or "Дом",
                "current": bool(house.get("is_current")),
                # дом, которым поделился другой человек: права на правку могут быть урезаны
                "shared": "sharing_info" in house,
            }
        )
        placed: set[str] = set()
        for room in house.get("rooms") or []:
            rooms.append(
                {"id": room.get("id"), "name": room.get("name"), "household_id": house_id}
            )
            for item in room.get("items") or []:
                if is_device(item) and item["id"] not in placed:
                    placed.add(item["id"])
                    flat.append((item, room.get("name"), room.get("id"), house_id))
        # всё, что не попало ни в одну комнату, — «Без комнаты»
        for item in house.get("all") or []:
            if is_device(item) and item["id"] not in placed:
                placed.add(item["id"])
                flat.append((item, None, None, house_id))
    return households, rooms, flat


async def _collect(
    hass: HomeAssistant, use_cache: bool = True, fresh: bool = False
) -> dict[str, Any]:
    """Список для панели. Сборки идут по одной.

    Две сборки разом делили бы паузу Станции и шли бы вдвое дольше каждая.
    Поэтому, пока список собирается, новый запрос ждёт эту сборку и получает
    её ответ. `fresh` — список нужен после правки: уже идущая сборка правку
    могла не увидеть, такой запрос встаёт в очередь за ней.
    """
    data = hass.data[DOMAIN]
    cache = data.get(DATA_CACHE)
    if use_cache and cache and time.time() - cache["ts"] < CACHE_TTL:
        return cache["payload"]

    running: asyncio.Task | None = data.get(DATA_BUILD)
    if running is not None and running.done():
        running = None
    if running is not None and not fresh:
        return await _wait_build(running)

    async def after_running() -> dict[str, Any]:
        if running is not None:
            await asyncio.wait([running])
        return await _build(hass)

    task = hass.async_create_background_task(after_running(), "yandex_menu: список")
    # все сборки очереди, чтобы при выгрузке остановить каждую, а не только последнюю
    builds: set[asyncio.Task] = data.setdefault(DATA_BUILDS, set())
    builds.add(task)

    def finished(done: asyncio.Task) -> None:
        builds.discard(done)
        # Ошибку получат все, кто ждёт; если ждать уже некому, пусть не сыплется в лог
        if not done.cancelled():
            done.exception()

    task.add_done_callback(finished)
    data[DATA_BUILD] = task
    return await _wait_build(task)


async def _wait_build(task: asyncio.Task) -> dict[str, Any]:
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        current = asyncio.current_task()
        if task.cancelled() and not (current and current.cancelling()):
            # сборку остановили: интеграцию перезапустили или удалили
            raise QuasarError(
                "Список не дочитан: интеграцию перезапустили. Откройте панель заново."
            ) from None
        raise


def _stop_build(hass: HomeAssistant) -> None:
    """Интеграцию выгружают — идущая сборка больше никому не нужна."""
    data = hass.data.get(DOMAIN, {})
    for task in list(data.get(DATA_BUILDS) or ()):
        task.cancel()
    data[DATA_BUILD] = None
    _publish_progress(hass, None)


def _forget_devices(hass: HomeAssistant) -> None:
    """«Обновить список»: всё, что помним об устройствах, читаем заново."""
    data = hass.data[DOMAIN]
    _touch(hass, *set(data.get(DATA_CONFIGS) or ()) | set(data.get(DATA_DETAILS) or ()))


def _known_skill_id(hass: HomeAssistant) -> str | None:
    """Навык Home Assistant в Яндексе — из того, что уже прочитано, без похода туда."""
    data = hass.data[DOMAIN]
    for holder in (data.get(DATA_CACHE), data.get(DATA_SAVED)):
        if holder and holder["payload"].get("skill_id"):
            return holder["payload"]["skill_id"]
    for _ts, config in (data.get(DATA_CONFIGS) or {}).values():
        if config.get("skill_id") and _is_ha_entity(hass, config.get("external_id")):
            return config["skill_id"]
    return None


def _save_devices(hass: HomeAssistant, owner: str) -> None:
    data = hass.data[DOMAIN]
    store = data.get(DATA_CACHE_STORE)
    if store is None or owner != account_key(hass) or data.get(DATA_CACHE_OWNER) != owner:
        return
    # Что писать, решаем в момент записи: за 30 с аккаунт могли сменить, и тогда
    # в кэше уже устройства нового — подписываем их новым владельцем
    store.async_delay_save(
        lambda: {
            "account": data.get(DATA_CACHE_OWNER),
            "configs": data.get(DATA_CONFIGS) or {},
            "details": data.get(DATA_DETAILS) or {},
        },
        30,
    )


def _touch(hass: HomeAssistant, *device_ids: str) -> None:
    """Устройство поменяли из панели — его настройки и карточку читаем заново.

    Счётчик нужен сборке, которая шла во время правки: она могла прочитать
    настройки ещё до правки, и такой ответ класть в кэш нельзя.
    """
    data = hass.data[DOMAIN]
    stale: dict[str, int] = data.setdefault(DATA_STALE, {})
    for device_id in device_ids:
        stale[device_id] = stale.get(device_id, 0) + 1
        data.setdefault(DATA_CONFIGS, {}).pop(device_id, None)
        data.setdefault(DATA_DETAILS, {}).pop(device_id, None)
    if device_ids:
        _save_devices(hass, account_key(hass))


def _publish_progress(hass: HomeAssistant, state: dict[str, Any] | None) -> None:
    data = hass.data[DOMAIN]
    data[DATA_PROGRESS] = state
    for send in list(data.get(DATA_PROGRESS_LISTENERS) or ()):
        send(state)


async def _build(hass: HomeAssistant) -> dict[str, Any]:
    """Собирает всё, что нужно панели, за один заход."""
    store_data = hass.data[DOMAIN]
    turn = next(_TURNS)
    owner = account_key(hass)
    account = station_entry(hass)
    # слепки тоже берём в начале: сменят аккаунт — чужие устройства в них не попадут
    snapshots: dict[str, Any] = store_data[DATA_SNAPSHOTS]
    api = _api(hass)
    raw = await api.devices()

    households, rooms, flat = _households_of(raw)

    semaphore = asyncio.Semaphore(PARALLEL_CONFIG_REQUESTS)

    async def read(coro, what: str, device_id: str) -> dict[str, Any] | None:
        try:
            return await coro
        except QuasarError as err:
            _LOGGER.debug("%s %s не прочиталась: %s", what, device_id, err)
            return None

    async def nothing(value: dict | None = None) -> dict | None:
        return value

    # Кэши берём в начале: сменят аккаунт — эта сборка пишет в старые и чужие
    # настройки новому аккаунту не достанутся
    details: dict[str, tuple[float, dict]] = store_data.setdefault(DATA_DETAILS, {})
    configs: dict[str, tuple[float, dict]] = store_data.setdefault(DATA_CONFIGS, {})
    stale: dict[str, int] = store_data.setdefault(DATA_STALE, {})

    def cached(store: dict[str, tuple[float, dict]], device_id: str, ttl: int) -> dict | None:
        hit = store.get(device_id)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        return None

    def needs_detail(device: dict[str, Any]) -> bool:
        # Настройки дают имена и сущность HA, карточка — умения с названиями
        return any(
            capability.get("type") in DETAIL_CAPABILITIES
            for capability in device.get("capabilities") or []
        )

    def config_hit(device: dict[str, Any]) -> dict | None:
        config = cached(configs, device["id"], CONFIG_TTL)
        # Основное имя сменили в приложении Яндекса — настройки устарели
        if config and config.get("name") and config["name"] != device.get("name"):
            return None
        return config

    def detail_hit(device: dict[str, Any]) -> dict | None:
        return cached(details, device["id"], DETAIL_TTL)

    shared_houses = {house["id"] for house in households if house["shared"]}

    async def remember(
        store: dict[str, tuple[float, dict]],
        device_id: str,
        coro,
        what: str,
        keys: tuple[str, ...],
        household_id: str | None,
    ) -> dict[str, Any] | None:
        mark = stale.get(device_id, 0)
        result = await read(coro, what, device_id)
        if stale.get(device_id, 0) != mark:
            return result
        if result:
            store[device_id] = (time.time(), {key: result[key] for key in keys if key in result})
        elif household_id in shared_houses:
            # В общем доме Яндекс настройки может не отдавать вовсе, и каждая
            # попытка стоит трёх запросов. Такой отказ помним. Сбой в своём
            # доме — нет: он разовый, в следующий раз прочитаем.
            store[device_id] = (time.time(), {})
        return result

    house_names = {house["id"]: house["name"] for house in households}
    todo = [
        placed
        for placed in flat
        if config_hit(placed[0]) is None
        or (needs_detail(placed[0]) and detail_hit(placed[0]) is None)
    ]
    started = time.monotonic()
    progress = {"house": None, "done": 0, "total": len(todo), "left": None}
    sent = 0.0
    published = False
    saved = time.monotonic()

    def step(household_id: str | None, done: bool) -> None:
        nonlocal sent, published, saved
        now = time.monotonic()
        if done and now - saved > SAVE_EVERY:
            # долгая сборка сохраняет прочитанное по ходу: перезапуск HA посреди
            # неё не должен начинать всё с нуля
            saved = now
            _save_devices(hass, owner)
        if done:
            progress["done"] += 1
            # устройство могли поменять из панели уже после подсчёта — оно сверх плана
            progress["total"] = max(progress["total"], progress["done"])
        else:
            progress["house"] = house_names.get(household_id)
        count, total = progress["done"], progress["total"]
        if count < total and now - sent < PROGRESS_EVERY:
            return
        sent = now
        # Скорость упирается в паузу Станции, так что оценка по первым
        # устройствам держится до конца
        pace = (now - started) / count if count >= PARALLEL_CONFIG_REQUESTS else 0.3
        progress["left"] = round(pace * (total - count))
        published = True
        _publish_progress(hass, dict(progress))

    async def load(placed: Placed) -> tuple[dict | None, dict | None]:
        device, _room, _room_id, household_id = placed
        config = config_hit(device)
        detail = detail_hit(device) if needs_detail(device) else None
        if config is not None and (detail is not None or not needs_detail(device)):
            return config, detail
        async with semaphore:
            step(household_id, done=False)
            config, detail = await asyncio.gather(
                remember(
                    configs,
                    device["id"],
                    api.device_config(device["id"]),
                    "Настройки",
                    CONFIG_KEYS,
                    household_id,
                )
                if config is None
                else nothing(config),
                remember(
                    details,
                    device["id"],
                    api.device(device["id"]),
                    "Карточка",
                    DETAIL_KEYS,
                    household_id,
                )
                if needs_detail(device) and detail is None
                else nothing(detail),
            )
            step(household_id, done=True)
        return config, detail

    loads = [asyncio.ensure_future(load(placed)) for placed in flat]
    try:
        loaded = await asyncio.gather(*loads)
    except BaseException:
        # сборку отменили или она упала — остальным устройствам в Яндекс ходить незачем
        for pending in loads:
            pending.cancel()
        raise
    finally:
        if published:
            _publish_progress(hass, None)
    if todo:
        _save_devices(hass, owner)

    devices: list[dict[str, Any]] = []
    skill_id: str | None = None

    for (device, room_name, room_id, household_id), (config, detail) in zip(
        flat, loaded, strict=True
    ):
        config = config or {}
        skills = _skills_of({**device, **(detail or {})})
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
            "household_id": household_id,
            "external_id": external_id,
            "from_ha": from_ha,
            "skill_id": config.get("skill_id"),
            "switchable": any(
                capability.get("type") == "devices.capabilities.on_off"
                for capability in (device.get("capabilities") or [])
            ),
            "skills": _skills_summary(skills),
            "abilities": skills,
            "on": _on_state(device),
        }
        if from_ha:
            entry["ha_state"] = hass.states.get(external_id) is not None
            _remember(snapshots, external_id, entry)
            if not skill_id and config.get("skill_id"):
                skill_id = config["skill_id"]
        devices.append(entry)

    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        lambda: hass.data[DOMAIN][DATA_STORE_DATA], 5
    )

    label = _label_info(hass)
    exposed = {
        device["external_id"] for device in devices if device.get("external_id")
    }
    unexposed = _unexposed_entities(hass, exposed)

    try:
        scenarios = _scenarios_of(await api.scenarios())
    except QuasarError as err:
        _LOGGER.debug("Сценарии не прочитались: %s", err)
        scenarios = None

    payload = {
        "devices": devices,
        "households": households,
        "rooms": rooms,
        "unexposed": unexposed,
        "label": label,
        "snapshots": snapshots,
        "max_names": MAX_NAMES,
        "skill_id": skill_id,
        "scenarios": scenarios,
        "stations": _stations(hass, flat),
        "account": {
            "name": account.title if account else None,
            "several": len(station_entries(hass)) > 1,
        },
    }
    if owner == account_key(hass):
        hass.data[DOMAIN][DATA_CACHE] = {"ts": time.time(), "payload": payload}
    _save_list(hass, payload, turn, owner)
    return payload


def _save_list(
    hass: HomeAssistant, payload: dict[str, Any], turn: int, owner: str
) -> None:
    """Запоминаем список, чтобы следующее открытие панели показало его сразу.

    Сборка идёт секунды, и за это время многое успевает смениться. Две сборки
    могут идти внахлёст: панель обновляет список, а человек тем временем
    переименовал лампу, — начатая раньше может закончиться позже, и её список
    уже старый. Могли сменить аккаунт или удалить интеграцию. Во всех этих
    случаях список не запоминаем.
    """
    data = hass.data[DOMAIN]
    store = data.get(DATA_SAVED_STORE)
    if store is None or owner != account_key(hass):
        return
    if turn < data.get(DATA_SAVED_TURN, 0):
        return
    data[DATA_SAVED_TURN] = turn
    data[DATA_SAVED] = {"account": owner, "ts": time.time(), "payload": payload}
    store.async_delay_save(lambda: data[DATA_SAVED], 10)


def _yaha_can_export(hass: HomeAssistant) -> Callable[[str, State | None], bool]:
    """Проверка «уйдёт ли сущность в Алису» по правилам самого Yandex Smart Home.

    Если его внутренности недоступны (другая версия), проверяем грубо:
    у датчика должен быть класс, иначе Яндекс не поймёт, что он измеряет.
    """

    def by_device_class(_entity_id: str, state: State | None) -> bool:
        return bool(state and state.attributes.get("device_class"))

    module = sys.modules.get(f"custom_components.{YAHA_DOMAIN}.device")
    component = hass.data.get(YAHA_DOMAIN)
    entry = yaha_entry(hass)
    if module is None or component is None or entry is None:
        return by_device_class
    try:
        entry_data = component.get_entry_data(entry)
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


async def _reply(
    hass,
    connection,
    msg,
    coro,
    remember: str | None = None,
    touch: str | None = None,
) -> None:
    """Выполняет действие и отвечает свежим списком.

    Если действие вернуло строку — она уедет в панель как примечание.
    `remember` — id устройства, чей слепок надо освежить принудительно.
    `touch` — устройство, которое действие меняет: его перечитаем, остальные
    возьмём из кэша.
    """
    notice: str | None = None
    changed = [device_id for device_id in (remember, touch) if device_id]
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
    finally:
        # и при ошибке: правка могла пройти наполовину
        _touch(hass, *changed)
    _drop_cache(hass)
    try:
        payload = await _collect(hass, use_cache=False, fresh=True)
    except QuasarError as err:
        connection.send_error(msg["id"], "quasar_error", str(err))
        return
    if remember:
        snapshots = hass.data[DOMAIN][DATA_SNAPSHOTS]
        for device in payload["devices"]:
            if device["id"] == remember and device.get("external_id"):
                _remember(snapshots, device["external_id"], device, force=True)
                hass.data[DOMAIN][DATA_STORE].async_delay_save(
                    lambda: hass.data[DOMAIN][DATA_STORE_DATA], 2
                )
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
@websocket_api.websocket_command({vol.Required("type"): "yandex_menu/list_saved"})
@callback
def ws_list_saved(hass: HomeAssistant, connection, msg) -> None:
    """Последний прочитанный список — сразу, без похода в Яндекс.

    Панель показывает его, пока в фоне собирается свежий. Ничего не запомнено
    (первое открытие, сменили аккаунт) — ответ пустой, и панель просто ждёт.
    """
    saved = hass.data.get(DOMAIN, {}).get(DATA_SAVED)
    if not saved:
        connection.send_result(msg["id"], None)
        return
    connection.send_result(msg["id"], {**saved["payload"], "saved_at": saved["ts"]})


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
        hass,
        connection,
        msg,
        _api(hass).set_room(msg["device_id"], msg["room_id"]),
        touch=msg["device_id"],
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
    await _reply(
        hass,
        connection,
        msg,
        _api(hass).delete_device(msg["device_id"]),
        touch=msg["device_id"],
    )


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
        skill_id = msg.get("skill_id") or _known_skill_id(hass)
        # «Обновить список» — и повод перечитать всё, что поменяли в приложении
        # Яндекса. Перечитает сборка ответа — уже после того, как Яндекс обновится.
        _forget_devices(hass)
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

    await _reply(hass, connection, msg, run(), touch=msg["device_id"])


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
        vol.Required("type"): "yandex_menu/say",
        vol.Required("entity_id"): str,
        vol.Required("text"): vol.All(str, vol.Length(min=1, max=200)),
    }
)
@websocket_api.async_response
async def ws_say(hass: HomeAssistant, connection, msg) -> None:
    """Станция выполняет фразу так, будто её сказали вслух."""
    entity = er.async_get(hass).async_get(msg["entity_id"])
    if not entity or entity.platform != YS_DOMAIN or entity.domain != "media_player":
        connection.send_error(msg["id"], "quasar_error", "Это не Яндекс.Станция.")
        return
    try:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": msg["entity_id"],
                "media_content_id": msg["text"].strip(),
                "media_content_type": "command",
            },
            blocking=True,
        )
    except Exception as err:  # noqa: BLE001 — показываем причину пользователю
        _LOGGER.debug("Станция не приняла фразу: %s", err)
        connection.send_error(
            msg["id"], "quasar_error", f"Станция не приняла команду: {err}"
        )
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

    await _reply(hass, connection, msg, run(), touch=msg["device_id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "yandex_menu/progress"})
@callback
def ws_progress(hass: HomeAssistant, connection, msg) -> None:
    """Подписка на ход сборки: какой дом читаем, сколько устройств осталось.

    Сразу после подписки приходит текущее состояние, дальше — изменения.
    None — сборки нет или ей нечего читать по одному.
    """
    listeners: set = hass.data[DOMAIN].setdefault(DATA_PROGRESS_LISTENERS, set())

    @callback
    def send(state: dict[str, Any] | None) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], state))

    listeners.add(send)
    connection.subscriptions[msg["id"]] = lambda: listeners.discard(send)
    connection.send_result(msg["id"])
    send(hass.data[DOMAIN].get(DATA_PROGRESS))


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (
        ws_list,
        ws_list_saved,
        ws_progress,
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
        ws_say,
    ):
        websocket_api.async_register_command(hass, command)
