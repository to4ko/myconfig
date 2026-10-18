"""Голосовые сценарии: карточки, облако и запуск Music Assistant."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import logging
import math
import re
import time
import uuid

from homeassistant.core import callback
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.config_entries import SIGNAL_CONFIG_ENTRY_CHANGED
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

try:
    from music_assistant_models.enums import RepeatMode
except ImportError:
    RepeatMode = None

from .accounts import account_key, station_entry
from .const import DATA_CACHE_OWNER, DATA_CONFIGS, DOMAIN
from . import library
from .voice_store import VoiceStore
from .quasar_api import QuasarError

_LOGGER = logging.getLogger(__name__)
MARKER = re.compile(r";;([,.:]+)$")
CONTROLS = {
    "next": {"title": "Следующий трек", "phrases": ["дальше", "следующий трек", "следующая песня", "следующая глава"]},
    "previous": {"title": "Предыдущий трек", "phrases": ["назад", "предыдущий трек", "предыдущая песня", "предыдущая глава"]},
    "resume": {"title": "Продолжить", "phrases": ["продолжи", "продолжай", "играй дальше"]},
    "restart": {"title": "Сначала", "phrases": ["сначала", "с начала", "включи сначала"]},
    "forward": {"title": "Вперёд на 30 с", "phrases": ["перемотай вперёд", "вперёд на 30 секунд", "промотай вперёд"]},
    "back": {"title": "Назад на 30 с", "phrases": ["перемотай назад", "назад на 30 секунд", "промотай назад"]},
    "shuffle_on": {"title": "Перемешать", "phrases": ["перемешай", "включи перемешивание", "в случайном порядке"]},
    "shuffle_off": {"title": "По порядку", "phrases": ["по порядку", "выключи перемешивание", "не перемешивай"]},
    "repeat_all": {"title": "Повторять всё", "phrases": ["повторяй", "повторяй всё", "включи повтор"]},
    "repeat_one": {"title": "Повторять трек", "phrases": ["повторяй трек", "повторяй эту песню"]},
    "repeat_off": {"title": "Без повтора", "phrases": ["не повторяй", "выключи повтор", "хватит повторять"]},
    "now_playing": {"title": "Что играет", "phrases": ["что играет", "что сейчас играет", "что это играет", "какая глава"]},
    "transfer": {"title": "Перенести сюда", "phrases": ["перенеси сюда", "играй здесь", "включи здесь", "перенеси музыку сюда"]},
}


def clean(value):
    return str(value).replace("---", "—")


def make_code(key, account, household):
    number = int.from_bytes(hashlib.sha256(f"{account}\0{household}\0{key}".encode()).digest()[:4], "big")
    result = ""
    while number:
        number, digit = divmod(number, 3)
        result += ",.:"[digit]
    return result or ","


def scenario_body(launch):
    title = library.clean_title(launch["title"], audiobook=launch.get("media", {}).get("media_type") == "audiobook")
    suffix = ";;" + launch["code"]
    control = launch.get("source") == "control"
    silent = control or launch.get("reply") == "silent"
    value = ("ничего не делай" if silent else "Включаю " + title)[:100-len(suffix)] + suffix
    icon = "⏯" if control else "▶"
    return {"name": f"{icon} {title} · Яндекс меню", "icon": "home",
            "household_id": launch["household_id"],
            "triggers": [{"type": "scenario.trigger.voice", "value": clean(p)} for p in launch["phrases"]],
            "steps": [{"type": "scenarios.steps.actions.v2", "parameters": {"items": [{
                "id": "requested-device", "type": "step.action.item.requested_device_with_assistant",
                "value": {"type": "devices.capabilities.quasar.server_action", "state": {
                    "instance": "text_action" if silent else "phrase_action", "value": value}}}]}}]}


def scenario_code(scenario):
    if not scenario.get("name", "").endswith(" · Яндекс меню"):
        return None
    for step in scenario.get("steps", []):
        for item in step.get("parameters", {}).get("items", []):
            if item.get("id") != "requested-device" or item.get("type") != "step.action.item.requested_device_with_assistant" or item.get("value", {}).get("type") != "devices.capabilities.quasar.server_action" or item.get("value", {}).get("state", {}).get("instance") not in ("phrase_action", "text_action"):
                continue
            value = item.get("value", {}).get("state", {}).get("value", "")
            match = MARKER.search(str(value))
            if match and "---" not in value:
                return match.group(1)
    return None


def launch_codes(launch):
    return {c for c in (launch.get("code"), launch.get("previous_code")) if c}


def owns_code(scenario, launch):
    return scenario_code(scenario) in launch_codes(launch)


def payload_matches(scenario, launch):
    expected = scenario_body(launch)
    phrases = [t.get("value") for t in scenario.get("triggers", []) if t.get("type") == "scenario.trigger.voice"]
    if scenario.get("name") != expected["name"] or phrases != launch.get("phrases"):
        return False
    wanted = expected["steps"][0]["parameters"]["items"][0]["value"]["state"]
    return any(item.get("value", {}).get("state") == wanted
               for step in scenario.get("steps", [])
               for item in step.get("parameters", {}).get("items", []))


def in_home(scenario, home):
    # Сценарий без дома Яндекс показывает во всех домах — значит, он и в этом
    if not scenario.get("household_ids") and not scenario.get("household_id"):
        return True
    return home in scenario.get("household_ids", []) or scenario.get("household_id") == home


def manual_key(media):
    if not isinstance(media, dict):
        return ""
    return str(media["uri"]) if media.get("uri") else json.dumps(media.get("uris") or [], ensure_ascii=False, separators=(",", ":"))


def exclusion_key(home, key):
    return json.dumps([home, key], ensure_ascii=False, separators=(",", ":"))


def normalized(value):
    return " ".join(clean(value).casefold().replace("ё", "е").split())


def snapshot_skips(snapshot, launch):
    """Пропущенная неоднозначная папка не доказывает исчезновение запуска."""
    return launch.get("key") in snapshot.get("skipped_keys", []) or any(
        warning.get("key") == launch.get("key") or
        (warning.get("provider_instance") == launch.get("provider_instance") and
         set(warning.get("identities", [])).intersection(launch.get("identities", [])))
        for warning in snapshot.get("warnings", []))


def current_chapter(queue):
    """Найти главу по позиции во всей книге."""
    media = library._get(library._get(queue, "current_item"), "media_item")
    chapters = sorted(library._get(library._get(media, "metadata"), "chapters") or [],
                      key=lambda chapter: library._get(chapter, "start"))
    elapsed = library._get(queue, "elapsed_time", 0) or 0
    current = next((i for i in range(len(chapters) - 1, -1, -1)
                    if library._get(chapters[i], "start") <= elapsed
                    and (library._get(chapters[i], "end") is None
                         or elapsed < library._get(chapters[i], "end"))), None)
    return chapters, current


class VoiceManager:
    def __init__(self, hass, entry, api):
        self.hass, self.entry, self.api = hass, entry, api
        self.account = account_key(hass)
        self.store = VoiceStore(hass, self.account)
        self.data = {"launches": {}, "excluded": [], "speaker_map": {}}
        self.locks = {}
        self.sync_lock = asyncio.Lock()
        self.cloud_lock = asyncio.Lock()
        self.sync_task = None
        self.tasks = set()
        self.commands = set()
        self.closed = False
        self.cloud = []
        self.scenario_cache = {}
        self.devices = []
        self.households = []
        self.results = {}
        self.debounce = {}
        self.snapshot = None
        self.mass_observed = None
        self.mass_unsubscribe = None
        self.scanning = set()
        self.mass_scanning = set()
        self.ingress_scanning = set()
        self.cloud_recovery_needed = False
        self.library_state = {"complete": False, "error": None, "syncing": False, "progress": None, "scan_scheduled": False, "scan_error": None}

    @property
    def launches(self):
        return self.data["launches"]

    def task(self, coro, background=False):
        if self.closed:
            coro.close()
            return None
        if background:
            task = self.entry.async_create_background_task(self.hass, coro, "Яндекс меню: библиотека")
        else:
            task = self.hass.async_create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def async_setup(self):
        self.data = await self.store.load()
        for key, default in (("launches", {}), ("excluded", []), ("speaker_map", {})):
            self.data.setdefault(key, default)
        if any(l.get("scenario_id") or (l.get("code") and l.get("state") in ("pending", "error")) for l in self.launches.values()):
            self.cloud_recovery_needed = True
            self.task(self.initial_recovery(), True)
        self.entry.async_on_unload(self.hass.bus.async_listen("yandex_speaker", self.on_event))
        self.entry.async_on_unload(async_track_time_interval(self.hass, self._interval, timedelta(minutes=10)))
        self.entry.async_on_unload(self.hass.bus.async_listen("component_loaded", self._component_loaded))
        self.entry.async_on_unload(async_dispatcher_connect(self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._entry_changed))
        self.entry.async_on_unload(self.close)
        if self.hass.is_running:
            self.task(self.refresh(), True)
        else:
            pending = True

            @callback
            def started(event):
                nonlocal pending
                pending = False
                self._interval(event)

            unsubscribe = self.hass.bus.async_listen_once("homeassistant_started", started)

            @callback
            def remove_started():
                nonlocal pending
                if pending:
                    pending = False
                    unsubscribe()

            self.entry.async_on_unload(remove_started)

    async def initial_recovery(self):
        try:
            await self.recover_cloud()
        except Exception:
            await self.retry_recovery()

    async def recover_cloud(self):
        async with self.cloud_lock:
            await self.read_cloud()
            self.cloud_recovery_needed = False

    async def retry_recovery(self):
        while self.cloud_recovery_needed:
            await asyncio.sleep(30)
            if not self.cloud_recovery_needed:
                return
            try:
                await self.recover_cloud()
            except Exception:
                _LOGGER.debug("Облако пока не готово к восстановлению голосовых запусков", exc_info=True)

    def loaded_ma_entry(self):
        for entry in self.hass.config_entries.async_entries("music_assistant"):
            if getattr(entry.state, "value", entry.state) == "loaded":
                return entry
        return None

    def ma_available(self):
        return self.loaded_ma_entry() is not None or library.get_mass(self.hass) is not None

    @callback
    def close(self):
        self.closed = True
        if self.mass_unsubscribe:
            self.mass_unsubscribe()
            self.mass_unsubscribe = None
        for task in tuple(self.tasks):
            task.cancel()

    @callback
    def _interval(self, _event):
        self.task(self.refresh(), True)

    @callback
    def _component_loaded(self, event):
        if event.data.get("component") == "music_assistant":
            self._interval(event)

    @callback
    def _entry_changed(self, _change, entry):
        if entry.domain == "music_assistant" and getattr(entry.state, "value", entry.state) == "loaded":
            self._interval(None)

    def _check_account(self):
        if account_key(self.hass) != self.account:
            raise ValueError("Аккаунт изменился — откройте панель заново")

    def _ensure_open(self):
        if self.closed:
            raise ValueError("Голосовые запуски отключены — откройте панель заново")

    def owns_scenario(self, scenario, launch):
        """Если форма недоступна, доверяем только сохранённому id в том же доме."""
        if not in_home(scenario, launch.get("household_id")):
            return False
        code = scenario_code(scenario)
        if code is not None:
            return code in launch_codes(launch)
        return bool(scenario.get("_detail_unavailable")
                    and scenario.get("id") == launch.get("scenario_id")
                    and scenario.get("name", "").endswith(" · Яндекс меню"))

    async def mutate_scenario(self, method, *args):
        # Потерянный ответ тоже может означать успешную запись.
        self.scenario_cache.clear()
        try:
            return await getattr(self.api, method)(*args)
        finally:
            self.scenario_cache.clear()

    async def read_cloud(self):
        self._check_account()
        listing = await self.api.scenarios_list()
        if isinstance(listing, dict):
            listing = listing.get("scenarios")
        if not isinstance(listing, list) or any(not isinstance(s, dict) or not s.get("id") for s in listing):
            raise ValueError("Яндекс не вернул полный список сценариев")
        present = {s["id"] for s in listing}
        self.scenario_cache = {ident: cached for ident, cached in self.scenario_cache.items() if ident in present}
        cloud = []
        for summary in listing:
            scenario = deepcopy(summary)
            if scenario.get("name", "").endswith(" · Яндекс меню"):
                ident = scenario["id"]
                fingerprint = json.dumps({key: scenario.get(key) for key in
                                          ("name", "triggers", "household_id", "household_ids")},
                                         sort_keys=True, ensure_ascii=False)
                cached = self.scenario_cache.get(ident)
                try:
                    if cached and cached[0] == fingerprint:
                        detail = cached[1]
                    else:
                        detail = await self.api.scenario_get(ident)
                        if not isinstance(detail, dict) or not isinstance(detail.get("steps"), list):
                            raise ValueError("Яндекс не вернул шаги сценария")
                        self.scenario_cache[ident] = (fingerprint, deepcopy(detail))
                    # Свежий список определяет имя, фразы и дом; форма нужна для шагов.
                    scenario["steps"] = deepcopy(detail["steps"])
                except Exception:
                    self.scenario_cache.pop(ident, None)
                    scenario.pop("steps", None)
                    scenario["_detail_unavailable"] = True
                    _LOGGER.debug("Не удалось прочитать шаги сценария %s", ident, exc_info=True)
            cloud.append(scenario)
        self.cloud = cloud
        raw = await self.api.devices()
        self.households = raw.get("households", [])
        self.devices = []
        for home in self.households:
            for room in home.get("rooms", []):
                for dev in room.get("items", room.get("devices", [])):
                    self.devices.append({**dev, "household_id": home["id"]})
            for dev in home.get("all", home.get("devices", [])):
                self.devices.append({**dev, "household_id": home["id"]})
        changed = False
        for launch in self.launches.values():
            found = [s for s in self.cloud if owns_code(s, launch) and in_home(s, launch.get("household_id"))]
            if len(found) == 1 and launch.get("state") in ("pending", "error"):
                if launch.get("scenario_id") != found[0]["id"]:
                    launch["scenario_id"] = found[0]["id"]
                    changed = True
                if not launch.get("cloud_dirty") or payload_matches(found[0], launch):
                    launch.update(state="active", last_error=None, cloud_dirty=False)
                    launch.pop("previous_code", None)
                    changed = True
        if changed:
            await self.store.save()
        self.cloud_recovery_needed = False

    def _home(self, msg):
        home = msg.get("household_id")
        if not home or home not in {h["id"] for h in self.households}:
            raise ValueError("Выберите существующий дом Яндекса")
        return home

    def _launch(self, msg):
        launch = self.launches.get(msg.get("launch_id"))
        if not launch or launch.get("household_id") not in (None, msg.get("household_id")):
            raise ValueError("Запуск не найден в этом доме")
        return launch

    def registry(self):
        return list(er.async_get(self.hass).entities.values())

    def speaker_rows(self):
        registry = self.registry()
        account = station_entry(self.hass)
        rows = []
        for entity in registry:
            if entity.platform != "yandex_station" or not entity.entity_id.startswith("media_player."):
                continue
            if account and getattr(entity, "config_entry_id", None) != account.entry_id:
                continue
            state = self.hass.states.get(entity.entity_id)
            attrs = state.attributes if state else {}
            info = attrs.get("quasar_info", {})
            device_ids = {str(entity.unique_id), str(info.get("device_id", "")), str(info.get("id", ""))}
            device = next((d for d in self.devices if str(d.get("id")) in device_ids or str(d.get("quasar_info", {}).get("device_id")) in device_ids), None)
            if not device:
                continue
            home = device.get("household_id")
            manual = self.data["speaker_map"].get(entity.entity_id)
            candidates = [e for e in registry if e.platform == "music_assistant" and e.entity_id.startswith("media_player.")]
            found = [e for e in candidates if e.entity_id == manual] if manual else [e for e in candidates if e.unique_id == entity.entity_id]
            if not found and not manual:
                qid = info.get("device_id") or device.get("quasar_info", {}).get("device_id")
                if qid:
                    found = [e for e in candidates if e.unique_id == "ys_" + str(qid)]
            reason = None
            if entity.disabled_by:
                reason = "Сущность Станции отключена"
            elif len(found) != 1:
                reason = "Найдено несколько игроков MA" if found else "Игрок MA не найден"
            elif found[0].disabled_by:
                reason = "Сущность MA отключена"
            elif self.hass.states.get(found[0].entity_id) is None:
                reason = "Сущность MA недоступна"
            rows.append({"entity_id": entity.entity_id, "name": attrs.get("friendly_name") or entity.original_name or entity.entity_id,
                         "household_id": home, "ma_entity_id": found[0].entity_id if len(found) == 1 else None, "reason": reason})
        return rows

    @callback
    def on_event(self, event):
        if self.closed:
            return
        try:
            data = event.data
            if data.get("instance") not in ("phrase_action", "text_action"):
                return
            value = str(data.get("value", ""))
            match = MARKER.search(value)
            if not match or "---" in value:
                return
            speaker = next((s for s in self.speaker_rows() if s["entity_id"] == data.get("entity_id")), None)
            if not speaker or not speaker.get("household_id"):
                return
            matches = [l for l in self.launches.values() if match.group(1) in launch_codes(l) and l.get("household_id") == speaker["household_id"] and l.get("scenario_id") and l.get("state") in ("active", "missing", "pending", "error")]
            launch = matches[0] if len(matches) == 1 else None
            if not launch:
                return
            self.task(self.dispatch_voice(launch, data.get("entity_id")))
        except Exception:
            _LOGGER.exception("Не удалось разобрать команду колонки")

    async def dispatch_voice(self, launch, entity_id):
        if self.closed:
            return
        try:
            self._check_account()
            speaker = next((s for s in self.speaker_rows() if s["entity_id"] == entity_id and s["household_id"] == launch.get("household_id")), None)
            if not speaker:
                message = "Колонка не найдена в доме запуска; проверьте подключение к облаку"
                _LOGGER.warning("%s: %s (%s)", message, entity_id, launch["id"])
                self.results[launch["id"]] = {"time": time.time(), "entity_id": entity_id,
                                              "speaker": entity_id, "success": False, "message": message}
                return
            key = (launch["id"], speaker["entity_id"])
            now = time.monotonic()
            if now - self.debounce.get(key, -10) < 3:
                return
            self.debounce[key] = now
            await self.play(launch, speaker)
        except Exception:
            _LOGGER.exception("Не удалось выполнить команду колонки")

    async def verify_manual_media(self, launch):
        """После удаления объекта MA ищем только однозначное совпадение имени и типа."""
        mass = library.get_mass(self.hass)
        media = launch["media"]
        getter = getattr(getattr(mass, "music", None), "get_item_by_uri", None)
        if launch.get("source") != "manual" or getter is None or not media.get("uri"):
            return True
        try:
            await getter(media["uri"])
        except Exception as err:
            self._ensure_open()
            if getattr(err, "error_code", None) != 2:
                raise
        else:
            self._ensure_open()
            if launch.pop("media_missing", None):
                await self.store.save()
            return True
        kind = media["media_type"]
        title = media.get("name") or launch["title"]
        response = await mass.music.search(search_query=title, media_types=[kind], limit=30, library_only=True)
        self._ensure_open()
        field = {"album": "albums", "audiobook": "audiobooks", "playlist": "playlists", "track": "tracks", "artist": "artists", "radio": "radio", "podcast": "podcasts"}.get(kind)
        values = response.get(field, []) if isinstance(response, dict) else getattr(response, field or "", [])
        matches = {}
        for item in values:
            get = item.get if isinstance(item, dict) else lambda k, default=None: getattr(item, k, default)
            item_kind = get("media_type", kind)
            item_kind = getattr(item_kind, "value", item_kind)
            if item_kind == kind and normalized(get("name", "")) == normalized(title) and get("uri"):
                matches[get("uri")] = item
        if len(matches) == 1:
            media["uri"] = next(iter(matches))
            launch["media_missing"] = False
            await self.store.save()
            return True
        launch["media_missing"] = True
        await self.store.save()
        return False

    async def play(self, launch, speaker):
        self._ensure_open()
        if launch.get("source") == "control":
            return await self.play_control(launch, speaker)
        error = None
        if not self.ma_available():
            error = "Music Assistant недоступен"
        elif speaker.get("reason") or not speaker.get("ma_entity_id"):
            error = "Не нашла, где играть на этой колонке"
        elif launch.get("state") == "missing":
            error = f"Не нашла {launch['title']} в библиотеке"
        else:
            media = launch["media"]
            try:
                found = await self.verify_manual_media(launch)
                self._ensure_open()
                if not found:
                    error = f"Не нашла {launch['title']} в библиотеке"
                else:
                    await self.hass.services.async_call("music_assistant", "play_media", {
                        "entity_id": speaker["ma_entity_id"], "media_id": media.get("uris") or media.get("uri"),
                        "media_type": "album" if media["media_type"] == "folder_artist" else media["media_type"], "enqueue": "replace"}, blocking=True)
            except Exception as err:
                self._ensure_open()
                error = "Music Assistant недоступен"
                _LOGGER.debug("MA не запустил %s: %s", launch["id"], err)
        result = {"time": time.time(), "entity_id": speaker["entity_id"], "speaker": speaker["name"], "success": error is None, "message": error or "играет"}
        self.results[launch["id"]] = result
        if error:
            self._ensure_open()
            try:
                await self.hass.services.async_call("media_player", "play_media", {"entity_id": speaker["entity_id"], "media_content_type": "text", "media_content_id": error}, blocking=True)
            except Exception:
                _LOGGER.debug("Не удалось произнести ошибку", exc_info=True)
        return result

    async def say_control(self, speaker, text):
        self._ensure_open()
        await self.hass.services.async_call("media_player", "play_media", {
            "entity_id": speaker["entity_id"], "media_content_type": "text",
            "media_content_id": text}, blocking=True)

    def now_playing_text(self, queue, speaker):
        item = library._get(queue, "current_item")
        if not item:
            state = self.hass.states.get(speaker["entity_id"])
            attrs = state.attributes if state else {}
            if state and state.state in ("playing", "paused") and attrs.get("media_title"):
                return ", ".join(str(v) for v in (attrs.get("media_artist"), attrs["media_title"]) if v)
            return "Сейчас ничего не играет"
        media = library._get(item, "media_item")
        title = library._get(media, "name") or library._get(item, "name") or "Без названия"
        kind = library._get(media, "media_type", library._get(item, "media_type"))
        if getattr(kind, "value", kind) == "audiobook":
            chapters, current = current_chapter(queue)
            if current is not None:
                title += f", глава {current + 1}"
                chapter_title = str(library._get(chapters[current], "title") or "").strip()
                if chapter_title and not re.fullmatch(r"(?:глава\s*)?\d+[.\s]*", chapter_title, re.IGNORECASE):
                    title += ", " + chapter_title
            return title
        artists = [library._get(artist, "name") for artist in library._get(media, "artists", []) or []]
        return ", ".join([str(name) for name in artists if name] + [title])

    async def station_control(self, action, speaker):
        state = self.hass.states.get(speaker["entity_id"])
        attrs = state.attributes if state else {}
        data = {"entity_id": speaker["entity_id"]}
        service = None
        if action in ("forward", "back"):
            if state and state.state == "playing":
                service = "media_seek"
                data["seek_position"] = max(0, (attrs.get("media_position") or 0) + (30 if action == "forward" else -30))
            nothing = "перематывать"
        elif action.startswith("shuffle_"):
            if (attrs.get("supported_features") or 0) & MediaPlayerEntityFeature.SHUFFLE_SET:
                service = "shuffle_set"
                data["shuffle"] = action == "shuffle_on"
            nothing = "перемешивать"
        else:
            if (attrs.get("supported_features") or 0) & MediaPlayerEntityFeature.REPEAT_SET:
                service = "repeat_set"
                data["repeat"] = action.removeprefix("repeat_")
            nothing = "повторять"
        if service:
            await self.hass.services.async_call("media_player", service, data, blocking=True)
            return "MA не играет — команда отдана станции"
        return "MA не играет — нечего " + nothing

    async def transfer_control(self, mass, target_queue, speaker):
        if mass is None or target_queue is None:
            raise ValueError("Очередь Music Assistant недоступна")
        candidates = []
        target_id = library._get(target_queue, "queue_id")
        registry = self.registry()
        for row in self.speaker_rows():
            if row["entity_id"] == speaker["entity_id"] or row.get("household_id") != speaker.get("household_id") or not row.get("ma_entity_id"):
                continue
            player = next((entity for entity in registry if entity.entity_id == row["ma_entity_id"] and entity.platform == "music_assistant"), None)
            if player is None:
                continue
            queue = await mass.player_queues.get_active_queue(player.unique_id)
            self._ensure_open()
            if not library._get(queue, "current_item") or library._get(queue, "queue_id") == target_id:
                continue
            state = library._get(queue, "state")
            if state is None:
                entity_state = self.hass.states.get(row["ma_entity_id"])
                state = entity_state.state if entity_state else None
            state = getattr(state, "value", state)
            if state in ("playing", "paused"):
                candidates.append((state == "playing", library._get(queue, "elapsed_time_last_updated", 0) or 0, row, queue))
        if not candidates:
            message = "на других колонках ничего не играет"
            await self.say_control(speaker, message)
            return message
        _, _, source, queue = max(candidates, key=lambda candidate: candidate[:2])
        await mass.player_queues.transfer(library._get(queue, "queue_id"), target_id, auto_play=True)
        return "перенесла с " + source["name"]

    async def play_control(self, launch, speaker):
        """Выполнить управление на услышавшей колонке."""
        success = True
        try:
            action = launch["media"]["action"]
            if action not in CONTROLS:
                raise ValueError("Неизвестная команда управления")
            ma_entity = speaker.get("ma_entity_id")
            state = self.hass.states.get(ma_entity) if ma_entity else None
            queue = None
            mass = library.get_mass(self.hass)
            if (state and state.state in ("playing", "paused") and not (action == "now_playing" and mass is None)) or action == "transfer":
                if mass is None:
                    raise ValueError("Клиент очереди Music Assistant недоступен")
                player = next((e for e in self.registry() if e.entity_id == ma_entity and e.platform == "music_assistant"), None)
                if player is None:
                    raise ValueError("Игрок Music Assistant не найден")
                queue = await mass.player_queues.get_active_queue(player.unique_id)
                self._ensure_open()
            item = library._get(queue, "current_item")
            if action == "transfer":
                message = await self.transfer_control(mass, queue, speaker)
            elif action == "now_playing":
                message = self.now_playing_text(queue, speaker)[:200]
                await self.say_control(speaker, message)
            elif not item and action in ("forward", "back", "shuffle_on", "shuffle_off", "repeat_all", "repeat_one", "repeat_off"):
                message = await self.station_control(action, speaker)
            elif not item and action == "resume" and library._get(queue, "current_index") is not None:
                # После рестарта HA очередь MA помнит номер, но не элемент: resume сам соберёт поток
                await mass.player_queues.resume(library._get(queue, "queue_id"))
                message = "продолжаю (перезапуск потока)"
            elif not item:
                if action == "restart":
                    message = "MA не играет — нечего включать сначала"
                else:
                    service = {"next": "media_next_track", "previous": "media_previous_track", "resume": "media_play"}[action]
                    await self.hass.services.async_call("media_player", service, {"entity_id": speaker["entity_id"]}, blocking=True)
                    message = "MA не играет — команда отдана станции"
            elif action in ("shuffle_on", "shuffle_off"):
                await mass.player_queues.shuffle(library._get(queue, "queue_id"), action == "shuffle_on")
                message = "перемешиваю" if action == "shuffle_on" else "по порядку"
            elif action.startswith("repeat_"):
                mode = action.removeprefix("repeat_")
                await mass.player_queues.repeat(library._get(queue, "queue_id"), RepeatMode(mode) if RepeatMode is not None else mode)
                message = {"all": "повторяю всё", "one": "повторяю трек", "off": "повтор выключен"}[mode]
            elif action in ("forward", "back"):
                position = max(1, int(library._get(queue, "elapsed_time", 0) or 0) + (30 if action == "forward" else -30))
                duration = library._get(item, "duration") or library._get(library._get(item, "media_item"), "duration")
                if action == "forward" and duration and position >= duration - 2:
                    message = "конец трека"
                else:
                    await mass.player_queues.seek(library._get(queue, "queue_id"), position)
                    message = "вперёд на 30 секунд" if action == "forward" else "назад на 30 секунд"
            elif action == "resume":
                current_index = library._get(queue, "current_index")
                elapsed = library._get(queue, "elapsed_time", 0) or 0
                restart_stream = False
                if state.state == "paused":
                    await self.hass.services.async_call("media_player", "media_play", {"entity_id": ma_entity}, blocking=True)
                    message = "продолжаю"
                    for _ in range(8):
                        self._ensure_open()
                        await asyncio.sleep(0.5)
                        self._ensure_open()
                        current_state = self.hass.states.get(ma_entity)
                        if current_state and current_state.state == "playing":
                            break
                    else:
                        restart_stream = True
                else:
                    station_state = self.hass.states.get(speaker["entity_id"])
                    restart_stream = not station_state or station_state.state != "playing"
                    message = "продолжаю" if restart_stream else "уже играет"
                if restart_stream and current_index is not None:
                    await mass.player_queues.play_index(library._get(queue, "queue_id"), current_index, seek_position=max(1, int(elapsed)))
                    message = "продолжаю (перезапуск потока)"
            elif action == "restart":
                # MA 2.10.6: позиция 0 = «не задана» → книга продолжилась бы с запомненного места
                await mass.player_queues.seek(library._get(queue, "queue_id"), 1)
                message = "с начала"
            else:
                media = library._get(item, "media_item")
                kind = library._get(media, "media_type", library._get(item, "media_type"))
                if getattr(kind, "value", kind) == "audiobook":
                    chapters, current = current_chapter(queue)
                    if current is None:
                        message = "Главы книги недоступны"
                    else:
                        target = current + 1 if action == "next" else max(0, current - 1)
                        if not 0 <= target < len(chapters):
                            message = "Последняя глава" if action == "next" else "Первая глава"
                        else:
                            await mass.player_queues.seek(library._get(queue, "queue_id"), max(1, math.ceil(library._get(chapters[target], "start"))))
                            message = "первая глава" if action == "previous" and current == 0 else f"глава {target+1}"
                elif action == "previous" and library._get(queue, "current_index") is not None:
                    current_index = library._get(queue, "current_index")
                    await mass.player_queues.play_index(library._get(queue, "queue_id"), max(0, current_index - 1))
                    message = "первый трек" if current_index == 0 else "предыдущий трек"
                else:
                    service = "media_next_track" if action == "next" else "media_previous_track"
                    await self.hass.services.async_call("media_player", service, {"entity_id": ma_entity}, blocking=True)
                    message = "следующий трек" if action == "next" else "предыдущий трек"
        except Exception:
            self._ensure_open()
            success = False
            message = "Не удалось выполнить команду управления"
            _LOGGER.exception("Не удалось выполнить управление %s на %s", launch["id"], speaker["entity_id"])
        result = {"time": time.time(), "entity_id": speaker["entity_id"], "speaker": speaker["name"], "success": success, "message": message}
        self.results[launch["id"]] = result
        return result

    async def refresh(self, scan=False, user_id=None):
        if self.closed:
            return self.library_state
        if self.sync_task and self.sync_task is not asyncio.current_task() and not self.sync_task.done():
            return await asyncio.shield(self.sync_task)
        self.sync_task = self.task(self._sync(scan, user_id), True)
        return await asyncio.shield(self.sync_task)

    async def _sync(self, scan, user_id=None):
        async with self.sync_lock:
            self.library_state["syncing"] = True
            try:
                self._check_account()
                mass = library.get_mass(self.hass)
                self.observe_mass(mass)
                if scan:
                    self.library_state.update(scan_scheduled=True, scan_error=None)
                if mass is None:
                    if scan:
                        self.library_state["scan_error"] = self._scan_error("Music Assistant недоступен")
                    self.library_state.update(complete=False, error="Доступны только ручные карточки: клиент библиотеки MA недоступен" if self.ma_available() else "Music Assistant недоступен")
                    for launch in self.launches.values():
                        if launch.get("source") != "control":
                            launch.update(missing_since=None, missing_confirmed=False)
                    await self.store.save()
                    return self.library_state
                if scan:
                    providers = [library._get(p, "instance_id") for p in library._providers(mass)]
                    self.ingress_scanning = set(providers)
                    self.scanning.update(providers)
                    try:
                        result = await library.ingress_scan(self.hass, user_id, providers, self._progress)
                        if not result.get("available"):
                            result = await library.scan_library(mass, self._progress)
                        self.library_state["scan_scheduled"] = result.get("scheduled", True)
                        self.library_state["scan_error"] = self._scan_error(result["error"]) if result.get("error") else None
                    finally:
                        self.ingress_scanning.clear()
                        self.scanning = set(self.mass_scanning)
                snapshot = await library.read_library(mass)
                self.snapshot = snapshot
                self.library_state.update(complete=snapshot["complete"], error=snapshot.get("error"), warnings=snapshot.get("warnings", []))
                if not snapshot["complete"]:
                    for launch in self.launches.values():
                        if launch.get("source") != "control":
                            launch.update(missing_since=None, missing_confirmed=False)
                    await self.store.save()
                    return self.library_state
                async with self.cloud_lock:
                    return await self.apply_snapshot(snapshot)
            except Exception as err:
                _LOGGER.exception("Не удалось синхронизировать голосовую библиотеку")
                self.library_state.update(complete=False, error=str(err))
                return self.library_state
            finally:
                self.library_state["syncing"] = False

    @staticmethod
    def _scan_error(error):
        return f"{error}. Запустите синхронизацию в Music Assistant: Настройки → Поставщики → <имя источника> → Синхронизировать"

    async def apply_snapshot(self, snapshot):
        now = time.time()
        incoming = [x for x in snapshot["launches"] if x["key"] not in self.data["excluded"]]
        seen = set()
        renamed = []
        # Сначала резервируем все существующие ключи по целому снимку.
        keys = {item["key"] for item in snapshot["launches"]}
        old = [l for l in self.launches.values() if l["source"] == "library"]
        def skipped(launch):
            return snapshot_skips(snapshot, launch)

        absent = [l for l in old if l["key"] not in keys and not skipped(l)]
        unmatched = [item for item in incoming if not any(l["key"] == item["key"] for l in old)]

        def related(launch, item):
            return (launch.get("media", {}).get("media_type") == item["media"].get("media_type")
                    and bool(set(item.get("identities", [])).intersection(launch.get("identities", []))))

        for item in incoming:
            ambiguity_warning = None
            matches = [l for l in old if l["key"] == item["key"]]
            candidates = [l for l in absent if related(l, item)]
            # Новая карточка неоднозначной папки уже могла появиться на прошлом
            # снимке; её точный ключ не доказывает исчезновение прежних объектов.
            if matches and candidates:
                seen.update(l["id"] for l in candidates)
                self.library_state["error"] = "Неоднозначное переименование: прежние карточки сохранены без изменений"
            if not matches:
                candidate_keys = {l["key"] for l in candidates}
                reverse = [other for other in unmatched if any(related(l, other) for l in candidates)]
                if len(candidate_keys) == 1 and len(reverse) == 1:
                    matches = candidates
                elif candidates:
                    seen.update(l["id"] for l in candidates)
                    ambiguity_warning = "Неоднозначное переименование: прежние карточки сохранены без изменений"
                    self.library_state["error"] = ambiguity_warning
            if not matches:
                ident = uuid.uuid4().hex
                launch = {"id": ident, "source": "library", "key": item["key"], "title": item["title"], "media": item["media"], "phrases": [], "reply": "phrase", "state": "waiting", "scenario_id": None, "household_id": None, "code": None, "pinned": False, "missing_since": None, "last_error": None}
                if ambiguity_warning:
                    launch.update(warning=ambiguity_warning, last_error={"message": ambiguity_warning})
                self.launches[ident] = launch
                matches = [launch]
            for launch in matches:
                seen.add(launch["id"])
                if launch.get("scenario_id") and ((not launch.get("title_override") and launch["title"] != item["title"]) or launch["media"] != item["media"] or launch.get("cloud_dirty") or launch.get("state") == "error"):
                    renamed.append(launch)
                    launch.update(cloud_dirty=True, state="error")
                if not launch.get("title_override"):
                    launch["title"] = item["title"]
                launch["source_title"] = item["title"]
                launch.update(key=item["key"], media=item["media"], identities=item.get("identities", []), provider_instance=item.get("provider_instance"), source_name=item.get("source_name"), albums=deepcopy(item.get("albums", [])), missing_since=None, missing_confirmed=False)
                if launch["state"] == "missing":
                    launch["state"] = "active" if launch.get("scenario_id") else "waiting"
        for ident, launch in list(self.launches.items()):
            if launch["source"] != "library" or ident in seen or skipped(launch):
                continue
            if launch.get("missing_since") is not None and now-launch["missing_since"] >= 600:
                launch["missing_confirmed"] = True
            if launch.get("scenario_id"):
                launch["state"] = "missing"
            elif launch.get("missing_since") is not None and now-launch["missing_since"] >= 600 and not launch.get("pinned"):
                del self.launches[ident]
                continue
            launch.setdefault("missing_since", None)
            if launch["missing_since"] is None:
                launch["missing_since"] = now
        await self.store.save()
        if renamed:
            try:
                await self.read_cloud()
            except Exception as err:
                for launch in renamed:
                    launch["last_error"] = {"message": str(err), "code": getattr(err, "code", None), "temporary": getattr(err, "temporary", False)}
                await self.store.save()
                self.library_state["error"] = str(err)
                return self.library_state
            for launch in renamed:
                found = next((s for s in self.cloud if s.get("id") == launch.get("scenario_id") and self.owns_scenario(s, launch)), None)
                if not found:
                    continue
                try:
                    launch["state"] = "pending"
                    await self.store.save()
                    await self.write_scenario(launch, scenario_body(launch))
                    launch["state"] = "active"
                    launch["cloud_dirty"] = False
                    launch["last_error"] = None
                except Exception as err:
                    launch["last_error"] = {"message": str(err), "code": getattr(err, "code", None), "temporary": getattr(err, "temporary", False)}
                    launch["state"] = "error"
                    if getattr(err, "temporary", False):
                        await self.store.save()
                        break
                await self.store.save()
        return self.library_state

    def observe_mass(self, mass):
        if mass is self.mass_observed:
            return
        if self.mass_unsubscribe:
            self.mass_unsubscribe()
        self.mass_observed = mass
        self.mass_unsubscribe = None
        self.mass_scanning.clear()
        self.scanning = set(self.ingress_scanning)
        if mass is None or not hasattr(mass, "subscribe"):
            return
        def updated(event):
            values = event.get("data") if isinstance(event, dict) else getattr(event, "data", None)
            if isinstance(values, list):
                self.mass_scanning = {library.task_provider(t) for t in library.scan_tasks(values)
                                      if library.task_active(t)}
                self.scanning = self.mass_scanning | self.ingress_scanning
        self.mass_unsubscribe = mass.subscribe(updated, ("sync_tasks_updated", "tasks_updated"))

    def refuse_unverified_create(self, launch, body):
        # Имя не доказывает владение и не позволяет привязать id. Но пока
        # шаги кандидата недоступны, новый POST может продублировать потерянный.
        if any(s.get("_detail_unavailable") and s.get("name") == body["name"]
               and s.get("name", "").endswith(" · Яндекс меню")
               and in_home(s, launch["household_id"]) for s in self.cloud):
            raise QuasarError(
                "Не удалось проверить существующий сценарий. Обновите список и повторите сохранение",
                temporary=True)

    async def write_scenario(self, launch, body):
        for attempt in range(2):
            if not launch.get("scenario_id"):
                self.refuse_unverified_create(launch, body)
            try:
                if launch.get("scenario_id"):
                    await self.mutate_scenario("scenario_update", launch["scenario_id"], body)
                    return launch["scenario_id"]
                result = await self.mutate_scenario("scenario_create", body)
                ident = (result.get("scenario_id") or result.get("id") or result.get("scenario", {}).get("id")) if isinstance(result, dict) else result
                if ident:
                    return ident
                await self.read_cloud()
                matches = [x for x in self.cloud if owns_code(x, launch) and in_home(x, launch["household_id"])]
                if len(matches) == 1:
                    return matches[0]["id"]
                raise ValueError("Яндекс не вернул id сценария; обновите список перед повтором")
            except Exception as err:
                if attempt or not getattr(err, "temporary", False):
                    raise
                await asyncio.sleep(0.5)
                creating = not launch.get("scenario_id")
                # POST мог пройти, даже когда ответ потерялся. Повтору предшествует чтение.
                await self.read_cloud()
                matches = [x for x in self.cloud if owns_code(x, launch) and in_home(x, launch["household_id"])]
                if len(matches) == 1 and (creating or (matches[0].get("id") == launch.get("scenario_id") and payload_matches(matches[0], launch))):
                    return matches[0]["id"]
                if len(matches) > 1:
                    raise ValueError("Несколько сценариев имеют один маркер") from err

    async def _progress(self, value):
        self.library_state["progress"] = value

    def validate(self, launch, phrases):
        errors, warnings = [], []
        if not isinstance(phrases, list) or not 1 <= len(phrases) <= 4:
            return ["Нужно от одной до четырёх фраз"], []
        norms = [normalized(p) for p in phrases]
        if any(not p or len(clean(raw)) > 100 for p, raw in zip(norms, phrases)):
            errors.append("Фраза пуста или длиннее 100 знаков")
        if len(norms) != len(set(norms)):
            errors.append("Фразы повторяются")
        home = launch["household_id"]
        used = set()
        for other in self.launches.values():
            if other["id"] != launch["id"] and other.get("household_id") == home:
                used.update(normalized(p) for p in other.get("phrases", []))
        for scenario in self.cloud:
            # Сценарий без дома Яндекс показывает во всех домах, как и панель.
            shared = not scenario.get("household_ids") and not scenario.get("household_id")
            if (in_home(scenario, home) or shared) and scenario.get("id") != launch.get("scenario_id") and not owns_code(scenario, launch):
                used.update(normalized(t.get("value", "")) for t in scenario.get("triggers", []) if t.get("type") == "scenario.trigger.voice")
        if used.intersection(norms):
            errors.append("Фраза занята другим сценарием в этом доме")
        device_names = {normalized(n) for d in self.devices if d.get("household_id") == home for n in [d.get("name", ""), *d.get("names", [])] if n}
        panel = self.hass.data.get(DOMAIN, {})
        if panel.get(DATA_CACHE_OWNER) == self.account:
            # Синонимы уже прочитаны общим списком: не запрашиваем каждый прибор заново.
            for device in self.devices:
                if device.get("household_id") != home:
                    continue
                cached = panel.get(DATA_CONFIGS, {}).get(device.get("id"))
                if isinstance(cached, (list, tuple)) and len(cached) == 2 and isinstance(cached[1], dict):
                    device_names.update(normalized(n) for n in cached[1].get("names", []) if n)
        for phrase in norms:
            if any(n in phrase or phrase in n for n in device_names):
                warnings.append("Фраза пересекается с именем устройства")
        return errors, list(dict.fromkeys(warnings))

    async def save(self, msg):
        control = msg.get("source") == "control"
        media = msg.get("media")
        if control and not msg.get("launch_id") and (not isinstance(media, dict) or media.get("media_type") != "control" or media.get("action") not in CONTROLS):
            raise ValueError("Выберите команду управления")
        key = "control:" + media["action"] if control and isinstance(media, dict) and media.get("action") in CONTROLS else manual_key(media)
        ident = msg.get("launch_id") or ("control:" if control else "manual:") + make_code(key, self.account, msg.get("household_id"))
        async with self.cloud_lock:
            async with self.locks.setdefault(ident, asyncio.Lock()):
                await self.read_cloud()
                home = self._home(msg)
                original = self._launch(msg) if msg.get("launch_id") else None
                if original:
                    if control and original.get("source") != "control":
                        raise ValueError("Нельзя заменить объект командой управления")
                    control = original.get("source") == "control"
                if control:
                    media = msg.get("media", original.get("media") if original else None)
                    if not isinstance(media, dict) or media.get("media_type") != "control" or media.get("action") not in CONTROLS:
                        raise ValueError("Выберите команду управления")
                    key = "control:" + media["action"]
                    if original and original.get("key") != key:
                        raise ValueError("Нельзя изменить вид команды управления")
                    existing = next((l for l in self.launches.values() if l.get("source") == "control" and l.get("key") == key and l.get("household_id") == home), None)
                    if existing and existing["id"] != ident:
                        raise ValueError("Команда управления уже существует в этом доме")
                launch = deepcopy(original) if original else {"id": ident, "source": "control" if control else "manual", "key": key, "state": "waiting", "scenario_id": None, "pinned": True, "missing_since": None}
                if not original and ident in self.launches:
                    if self.launches[ident].get("source") != ("control" if control else "manual") or self.launches[ident].get("key") != key:
                        raise ValueError("Маркер совпал с другим объектом Music Assistant")
                    launch = deepcopy(self.launches[ident])
                    if launch.get("household_id") != home:
                        raise ValueError("Запуск принадлежит другому дому")
                if control:
                    definition = CONTROLS[media["action"]]
                    title = definition["title"]
                    media = {"media_type": "control", "action": media["action"]}
                else:
                    title = library.clean_title(msg.get("title", launch.get("title", "")), audiobook=launch.get("media", msg.get("media", {})).get("media_type") == "audiobook")
                    media = msg.get("media", launch.get("media"))
                    if not title or not isinstance(media, dict) or media.get("media_type") == "control" or not media.get("media_type") or not (media.get("uri") or media.get("uris")):
                        raise ValueError("Укажите название и объект Music Assistant")
                reply = "silent" if control else msg.get("reply", launch.get("reply", "phrase"))
                if reply not in ("phrase", "silent"):
                    raise ValueError("Неизвестный ответ Алисы")
                saved_code = launch.get("code")
                launch.pop("media_missing", None)
                launch.update(title_override=bool(original and title != original.get("source_title", original.get("title"))), title=title, media=deepcopy(media), household_id=home, reply=reply, code=launch.get("code") or make_code(launch["key"], self.account, home))
                own = [s for s in self.cloud if self.owns_scenario(s, launch)]
                if len(own) > 1:
                    raise ValueError("Несколько сценариев имеют один маркер; разберите сироты")
                if own and not saved_code:
                    raise ValueError("Маркер занят другим сценарием")
                if own:
                    launch["scenario_id"] = own[0]["id"]
                phrases = msg.get("phrases", launch.get("phrases", definition["phrases"] if control else []))
                errors, warnings = self.validate(launch, phrases)
                if errors:
                    return {"errors": errors, "warnings": warnings}
                if warnings and not msg.get("confirm_warnings"):
                    return {"needs_confirmation": True, "warnings": warnings}
                launch["phrases"] = [clean(p).strip() for p in phrases]
                existing = [s for s in self.cloud if self.owns_scenario(s, launch)]
                if len(existing) > 1:
                    raise ValueError("Несколько сценариев имеют один маркер; разберите сироты")
                if existing:
                    launch["scenario_id"] = existing[0]["id"]
                elif any(s.get("id") == launch.get("scenario_id") for s in self.cloud):
                    raise ValueError("Сценарий не принадлежит этому запуску")
                else:
                    # Только полный успешный список доказывает отсутствие id.
                    launch["scenario_id"] = None
                new_code = make_code(launch["key"], self.account, home)
                if any(other["id"] != ident and other.get("household_id") == home and new_code in launch_codes(other) for other in self.launches.values()):
                    raise ValueError("Маркер совпал с другим запуском")
                if any(scenario_code(s) == new_code and in_home(s, home) and s.get("id") != launch.get("scenario_id") for s in self.cloud):
                    raise ValueError("Маркер занят другим сценарием")
                if launch["code"] != new_code:
                    launch["previous_code"] = launch["code"]
                    launch["code"] = new_code
                launch["cloud_dirty"] = bool(launch.get("scenario_id"))
                launch["state"] = "pending"
                self.launches[ident] = launch
                await self.store.save()
                try:
                    body = scenario_body(launch)
                    launch["scenario_id"] = await self.write_scenario(launch, body)
                    launch.update(state="active", last_error=None, cloud_dirty=False)
                    launch.pop("previous_code", None)
                    await self.store.save()
                except Exception as err:
                    launch["last_error"] = {"message": str(err), "code": getattr(err, "code", None), "temporary": getattr(err, "temporary", False)}
                    if not getattr(err, "temporary", False):
                        launch["state"] = "error"
                    await self.store.save()
                    raise
                return {"launch": deepcopy(launch)}

    async def remove_scenario(self, launch):
        ident = launch.get("scenario_id")
        if ident:
            found = next((s for s in self.cloud if s.get("id") == ident), None)
            if found and not self.owns_scenario(found, launch):
                raise ValueError("Сценарий не принадлежит этому запуску")
            if found:
                await self.mutate_scenario("scenario_delete", ident)
                self.cloud.remove(found)
            launch.update(scenario_id=None, state="waiting", last_error=None)
            await self.store.save()

    def orphans(self, home):
        known = {l.get("scenario_id") for l in self.launches.values()}
        result = []
        for scenario in self.cloud:
            code = scenario_code(scenario)
            if not in_home(scenario, home) or not code or scenario.get("id") in known:
                continue
            matches = [l for l in self.launches.values() if l.get("household_id") == home and code in launch_codes(l) and not l.get("scenario_id")]
            can_bind = len(matches) == 1
            result.append({**scenario, "code": code, "can_bind": can_bind, "reason": None if can_bind else "Нет однозначной сохранённой карточки с объектом MA; сценарий не хранит, что играть", "bind_reason": None if can_bind else "Нет однозначной сохранённой карточки с объектом MA; сценарий не хранит, что играть"})
        return result

    def health(self):
        station = station_entry(self.hass)
        quasar = self.hass.data.get("yandex_station", {}).get(station.unique_id) if station else None
        updates = getattr(quasar, "updates_task", None)
        config = self.hass.data.get("yandex_station", {}).get("config", {})
        return {"ma_available": self.ma_available(), "cloud_updates": bool(config.get("cloud_updates", True)), "updates_running": bool(updates and not updates.done()), "manual_only": library.get_mass(self.hass) is None}

    async def command(self, action, msg, user_id=None):
        if self.closed:
            raise ValueError("Голосовые запуски отключены — откройте панель заново")
        operation = self.hass.async_create_task(self._command(action, msg, user_id))
        self.commands.add(operation)
        operation.add_done_callback(self.commands.discard)
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            # Принятая операция должна завершить облачную запись и durable save.
            await asyncio.shield(operation)
            raise

    async def _command(self, action, msg, user_id=None):
        self._check_account()
        if action == "save":
            return await self.save(msg)
        if action in ("refresh", "search"):
            if not self.households:
                async with self.cloud_lock:
                    await self.read_cloud()
            self._home(msg)
        if action == "refresh":
            if msg.get("cancel"):
                if self.sync_task and not self.sync_task.done():
                    self.sync_task.cancel()
                self.library_state.update(syncing=False, progress=None)
                return {"cancelled": True}
            if not self.sync_task or self.sync_task.done():
                self.library_state.update(syncing=True, progress=None, scan_scheduled=True, scan_error=None)
                self.sync_task = self.task(self._sync(True, user_id), True)
            return {"library": deepcopy(self.library_state)}
        if action == "search":
            if not self.ma_available():
                return {"items": [], "error": "Music Assistant недоступен"}
            query = str(msg.get("query", "")).strip()
            if not query:
                return {"items": []}
            try:
                mass = library.get_mass(self.hass)
                if mass is not None:
                    response = await mass.music.search(search_query=query, media_types=["album", "audiobook", "playlist"], limit=30, library_only=True)
                else:
                    entry = self.loaded_ma_entry()
                    response = await self.hass.services.async_call("music_assistant", "search", {"config_entry_id": entry.entry_id, "name": query, "media_type": ["album", "audiobook", "playlist"], "limit": 30, "library_only": True}, blocking=True, return_response=True)
                items = []
                for kind, field in (("album", "albums"), ("audiobook", "audiobooks"), ("playlist", "playlists")):
                    values = response.get(field, []) if isinstance(response, dict) else getattr(response, field, [])
                    for item in values:
                        get = item.get if isinstance(item, dict) else lambda k, default=None: getattr(item, k, default)
                        image = get("image")
                        if mass is not None and hasattr(mass, "get_media_item_image_url"):
                            try:
                                image = mass.get_media_item_image_url(item)
                            except Exception:
                                image = None
                        items.append({"image": image, "title": get("name", ""), "media": {"media_type": kind, "uri": get("uri")}, "uri": get("uri"), "media_type": kind, "name": get("name", "")})
                return {"items": items}
            except Exception as err:
                return {"items": [], "error": str(err)}
        async with self.cloud_lock:
            if action != "state" or not msg.get("cached") or not self.households:
                await self.read_cloud()
            home = self._home(msg)
            if action == "state":
                changed = False
                for template in list(self.launches.values()):
                    if template.get("source") != "library" or template["key"] in self.data["excluded"] or exclusion_key(home, template["key"]) in self.data["excluded"]:
                        continue
                    if any(l.get("source") == "library" and l.get("key") == template["key"] and l.get("household_id") == home for l in self.launches.values()):
                        continue
                    clone = deepcopy(template)
                    ident = uuid.uuid4().hex
                    clone.update(id=ident, household_id=home, scenario_id=None, code=None, previous_code=None, state="missing" if template.get("state") == "missing" else "waiting", phrases=[], last_error=None, cloud_dirty=False)
                    self.launches[ident] = clone
                    changed = True
                if changed:
                    await self.store.save()
                speakers = [s for s in self.speaker_rows() if s["household_id"] == home]
                launches = []
                by_id = {s["id"]: s for s in self.cloud}
                for launch in self.launches.values():
                    if launch.get("household_id") != home:
                        continue
                    item = deepcopy(launch)
                    item["last_result"] = self.results.get(item["id"])
                    scenario = by_id.get(item.get("scenario_id"))
                    if item.get("scenario_id") and scenario is None:
                        item["cloud_error"] = "Сценарий удалён в приложении — создать заново"
                    elif scenario and [t.get("value") for t in scenario.get("triggers", [])] != item.get("phrases"):
                        item["cloud_error"] = "Изменён в приложении"
                    launches.append(item)
                return {"launches": launches, "library": deepcopy(self.library_state), "speakers": speakers,
                        "players": [{"entity_id": e.entity_id, "name": e.original_name or e.entity_id} for e in self.registry() if e.entity_id.startswith("media_player.") and e.platform == "music_assistant" and not e.disabled_by],
                        "health": self.health(), "orphans": self.orphans(home),
                        "scenarios": [{"id": s.get("id"), "name": s.get("name", ""),
                                       "phrases": [t.get("value") for t in s.get("triggers", []) if t.get("type") == "scenario.trigger.voice"],
                                       "households": s.get("household_ids") or ([s["household_id"]] if s.get("household_id") else [])}
                                      for s in self.cloud if in_home(s, home) or not (s.get("household_ids") or s.get("household_id"))]}
            if action == "speaker_map":
                speaker = next((s for s in self.speaker_rows() if s["entity_id"] == msg.get("entity_id") and s["household_id"] == home), None)
                if speaker is None:
                    raise ValueError("Колонка не найдена в этом доме")
                target = msg.get("ma_entity_id")
                if target and not any(e.entity_id == target and e.entity_id.startswith("media_player.") and e.platform == "music_assistant" and not e.disabled_by for e in self.registry()):
                    raise ValueError("Игрок MA не найден")
                if target:
                    self.data["speaker_map"][speaker["entity_id"]] = target
                else:
                    self.data["speaker_map"].pop(speaker["entity_id"], None)
                await self.store.save()
                return {"saved": True}
            if action == "orphans":
                operation = msg.get("action") or msg.get("operation") or msg.get("orphan_action")
                orphans = self.orphans(home)
                if msg.get("scenario_id"):
                    orphans = [s for s in orphans if s["id"] == msg["scenario_id"]]
                    if not orphans:
                        raise ValueError("Сценарий уже привязан или не найден среди сирот этого дома")
                count = 0
                skipped = []
                for scenario in orphans:
                    if operation == "delete":
                        await self.mutate_scenario("scenario_delete", scenario["id"])
                        self.cloud.remove(next(s for s in self.cloud if s["id"] == scenario["id"]))
                        await self.store.save()
                    elif operation == "bind":
                        matches = [l for l in self.launches.values() if l.get("household_id") == home and scenario["code"] in launch_codes(l)]
                        if len(matches) != 1 or matches[0].get("scenario_id"):
                            reason = scenario.get("bind_reason") or "Нет однозначной сохранённой карточки"
                            if msg.get("scenario_id"):
                                raise ValueError(reason)
                            skipped.append({"scenario_id": scenario["id"], "reason": reason})
                            continue
                        matches[0].update(scenario_id=scenario["id"], state="active", last_error=None)
                        await self.store.save()
                    else:
                        raise ValueError("Выберите привязку или удаление")
                    count += 1
                return {"count": count, "bound": count if operation == "bind" else 0, "deleted": count if operation == "delete" else 0, "skipped": len(skipped), "skipped_details": skipped, "reason": "Часть сценариев не содержит восстанавливаемой карточки MA" if skipped else None}
            if action == "deactivate_all":
                launches = sorted((l for l in self.launches.values() if l.get("household_id") == home and l.get("scenario_id")), key=lambda l: l["id"])
                for launch in launches:
                    async with self.locks.setdefault(launch["id"], asyncio.Lock()):
                        await self.remove_scenario(launch)
                return {"count": len(launches)}
            if action == "delete_missing":
                mass = library.get_mass(self.hass)
                if mass is None:
                    raise ValueError("Music Assistant недоступен")
                snapshot = await library.read_library(mass)
                if not snapshot or not snapshot.get("complete"):
                    raise ValueError("Нужен полный снимок библиотеки")
                sources = snapshot.get("sources", {})
                present = {x["key"] for x in snapshot.get("launches", [])}
                now = time.time()
                missing = [l for l in self.launches.values() if l.get("source") != "control" and l.get("household_id") == home and l.get("state") == "missing" and l.get("scenario_id")]
                # MA item_id уникален внутри media table, а ключ папки может
                # измениться. Проверяем весь набор до первого облачного DELETE.
                def media_table(item):
                    kind = item.get("media", {}).get("media_type")
                    return "album" if kind == "folder_artist" else kind

                if any(item.get("key") != launch.get("key")
                       and item.get("provider_instance") == launch.get("provider_instance")
                       and media_table(item) == media_table(launch)
                       and set(item.get("identities", [])).intersection(launch.get("identities", []))
                       for launch in missing for item in snapshot.get("launches", [])):
                    raise ValueError("Объект найден в библиотеке под другим ключом. Обновите библиотеку и проверьте перепривязку карточки; массовое удаление остановлено")
                eligible = [l for l in missing if not snapshot_skips(snapshot, l) and l["key"] not in present and l.get("provider_instance") not in self.scanning and not l.get("pinned") and l.get("missing_confirmed") and l.get("missing_since") is not None and now-l["missing_since"] >= 600 and sources.get(l.get("provider_instance"), {}).get("healthy") and sources.get(l.get("provider_instance"), {}).get("items", 0) > 0 and not self.library_state.get("scan_scheduled")]
                if len(eligible) != len(missing):
                    raise ValueError("Источник недоступен или карточка закреплена; массовое удаление остановлено")
                for launch in sorted(eligible, key=lambda l: l["id"]):
                    async with self.locks.setdefault(launch["id"], asyncio.Lock()):
                        await self.remove_scenario(launch)
                return {"count": len(eligible)}
            launch = self._launch(msg)
            async with self.locks.setdefault(launch["id"], asyncio.Lock()):
                if action == "test":
                    speaker = next((s for s in self.speaker_rows() if s["entity_id"] == msg.get("entity_id") and s["household_id"] == home), None)
                    if not speaker:
                        raise ValueError("Колонка не найдена в этом доме")
                    return {"result": await self.play(launch, speaker)}
                if action not in ("deactivate", "delete", "exclude"):
                    raise ValueError("Неизвестная команда")
                if action == "exclude" and launch["source"] == "control":
                    raise ValueError("Для команды управления выберите «Выключить»")
                if action == "delete" and launch["source"] not in ("manual", "control"):
                    raise ValueError("Для библиотечной карточки выберите «Не показывать»")
                await self.remove_scenario(launch)
                if action in ("delete", "exclude"):
                    if action == "exclude":
                        excluded = exclusion_key(home, launch["key"])
                        if excluded not in self.data["excluded"]:
                            self.data["excluded"].append(excluded)
                    del self.launches[launch["id"]]
                await self.store.save()
                return {"saved": True}

    async def async_unload(self):
        tasks = tuple(self.tasks)
        self.close()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.commands:
            await asyncio.gather(*tuple(self.commands), return_exceptions=True)
        await self.store.save()
