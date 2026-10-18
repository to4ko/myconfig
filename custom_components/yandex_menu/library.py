"""Чтение файловой библиотеки Music Assistant без отдельного клиента."""
from __future__ import annotations

import asyncio
import inspect
import os
import re
from typing import Any
from urllib.parse import urlsplit

import aiohttp

PAGE_SIZE = 200
SCAN_TIMEOUT = 300
SCAN_POLL_INTERVAL = 2
FILE_PROVIDERS = {"filesystem_local", "filesystem_smb"}
SCAN_AUTH_ERROR = ("Music Assistant не дал запустить скан: ваш пользователь Home Assistant "
                   "должен быть администратором в Music Assistant")


def _get(obj: Any, key: str, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def get_mass(hass):
    """Вернуть клиент только загруженной записи интеграции MA."""
    try:
        for entry in hass.config_entries.async_entries("music_assistant"):
            if _get(entry.state, "value", entry.state) != "loaded":
                continue
            if mass := getattr(getattr(entry, "runtime_data", None), "mass", None):
                return mass
    except (AttributeError, TypeError):
        pass
    return None


def _providers(mass):
    return [p for p in getattr(mass, "providers", ()) if _get(p, "domain") in FILE_PROVIDERS]


def _parts(path):
    if not isinstance(path, str) or path.startswith(("/", "\\")):
        return []
    parts = path.replace("\\", "/").split("/")
    if not parts or any(not p or p.startswith(("_", ".")) for p in parts):
        return []
    return parts


def clean_title(value, *, audiobook=False):
    """Убрать технические метки и чтеца из имени коллекции."""
    title = str(value).replace("---", "—")
    title = re.sub(r"\[[^]\n]*\]", " ", title)
    title = re.sub(r"\b\d{4}-\d{2}-\d{2}\b|\(\d{4}\)", " ", title)
    title = re.sub(r"\b(?:\d{2,4}\s*(?:kbps|кбит(?:/с)?|kb/s)|FLAC|MP3)\b", " ", title, flags=re.I)
    title = re.sub(r"\s*\([^()]*\)\s*$", "", title)
    if audiobook and " — " in title:
        title = title.split(" — ", 1)[1]
    title = " ".join(re.sub(r"[\W_]", " ", title).split())
    return " ".join(title.split()[:6])[:60].rstrip()


def _sort_album(row):
    name = row["path"][1] if len(row["path"]) > 1 else row["path"][0]
    date = re.search(r"\d{4}-\d{2}-\d{2}", name)
    return (date.group() if date else name.casefold(), name.casefold(), row["uri"])


async def read_library(mass) -> dict:
    """Получить полный снимок; неполный снимок нельзя применять к карточкам."""
    result = {"complete": False, "launches": [], "providers": [], "error": None,
              "sources_healthy": False, "sources": {}, "warnings": [], "skipped_keys": []}
    if mass is None:
        result["error"] = "Music Assistant недоступен"
        return result
    try:
        providers = _providers(mass)
        ids = {_get(p, "instance_id") for p in providers}
        source_names = {_get(p, "instance_id"): _get(p, "name") or _get(p, "domain") for p in providers}
        result["providers"] = sorted(ids)
        source_health = {_get(p, "instance_id"): bool(_get(p, "available", False))
                         for p in providers}
        grouped = {}
        objects = {p: set() for p in ids}
        for kind, method in (("album", mass.music.get_library_albums),
                             ("audiobook", mass.music.get_library_audiobooks)):
            offset = 0
            while True:
                page = await method(limit=PAGE_SIZE, offset=offset, order_by="sort_name")
                for item in page:
                    uri = _get(item, "uri")
                    if not uri:
                        raise ValueError("MA вернул объект без URI")
                    for mapping in _get(item, "provider_mappings", ()):
                        provider = _get(mapping, "provider_instance")
                        if provider not in ids:
                            continue
                        objects[provider].add((kind, uri))
                        if not _get(mapping, "available", True):
                            source_health[provider] = False
                        parts = _parts(_get(mapping, "item_id"))
                        if not parts:
                            continue
                        # У книги путь указывает на первую главу, у альбома — на папку.
                        if kind == "audiobook" and len(parts) < 2:
                            continue
                        # У ProviderInstance нет content_type: используем тип объекта.
                        # Второй сегмент используем ниже только для нескольких книг
                        # автора: у одной книги это может быть папка диска с главами.
                        folder = parts[0]
                        grouped.setdefault((provider, folder), []).append({
                            "kind": kind, "path": parts, "uri": uri,
                            "title": _get(item, "name", parts[0]),
                            "identity": f"{provider}|{_get(item, 'item_id')}",
                        })
                offset += len(page)
                if len(page) < PAGE_SIZE:
                    break
        # Собираем книги одной верхней папки до формирования ключей: автор
        # может содержать одновременно однофайловые книги и папки с главами.
        books_by_top = {}
        for (provider, _), rows in grouped.items():
            for row in rows:
                if row["kind"] == "audiobook":
                    books_by_top.setdefault((provider, row["path"][0]), set()).add(row["uri"])
        regrouped = {}
        for (provider, folder), rows in grouped.items():
            for row in rows:
                row_folder = folder
                if (row["kind"] == "audiobook"
                        and len(books_by_top[(provider, row["path"][0])]) > 1):
                    row_folder = "/".join(row["path"][:2])
                regrouped.setdefault((provider, row_folder), []).append(row)
        launches = []
        for (provider, top), rows in sorted(regrouped.items()):
            # Один объект может иметь несколько mappings в одной верхней папке.
            rows = list({(r["kind"], r["uri"]): r for r in rows}.values())
            albums = [r for r in rows if r["kind"] == "album"]
            subfolders = {r["path"][1] for r in albums if len(r["path"]) > 1}
            if (len(subfolders) >= 2 and all(len(r["path"]) > 1 for r in albums)
                    and len(albums) == len(rows)):
                media = {"media_type": "folder_artist", "uris": [r["uri"] for r in sorted(albums, key=_sort_album)]}
                title = top
                ordered_albums = sorted(albums, key=_sort_album)
            elif len(rows) == 1:
                media = {"media_type": rows[0]["kind"], "uri": rows[0]["uri"]}
                title = rows[0]["title"]
            else:
                # Не выбираем случайную книгу/альбом при неоднозначной раскладке.
                key = f"{provider}|{top}"
                result["skipped_keys"].append(key)
                result["warnings"].append({
                    "key": key, "folder": top, "reason": "несколько книг/альбомов",
                    "provider_instance": provider,
                    "identities": sorted({r["identity"] for r in rows}),
                })
                continue
            launches.append({"source": "library", "key": f"{provider}|{top}", "title": clean_title(title, audiobook=media["media_type"] == "audiobook") or clean_title(top),
                             "source_name": source_names[provider],
                             "albums": [{"title": clean_title(r["title"]) or clean_title(r["path"][-1]), "uri": r["uri"]} for r in ordered_albums] if media["media_type"] == "folder_artist" else [],
                             "media": media, "provider_instance": provider,
                             "identities": sorted({r["identity"] for r in rows})})
        result.update(complete=True, launches=launches,
                      sources_healthy=bool(ids) and all(source_health[p] and objects[p] for p in ids),
                      sources={p: {"healthy": source_health[p] and bool(objects[p]),
                                   "items": len(objects[p])} for p in sorted(ids)})
    except Exception as err:
        result["error"] = str(err) or type(err).__name__
    return result


def task_provider(task):
    """Источник задачи в новом и прежнем протоколе MA."""
    return _get(_get(task, "metadata", {}), "provider_instance") or _get(task, "provider_instance")


def task_active(task):
    """В старом протоколе список содержит только выполняющиеся задачи."""
    status = _get(task, "status")
    return status in ("pending", "running") or (status is None and not _get(task, "metadata"))


def scan_tasks(data, providers=None):
    """Выбрать задачи синхронизации, включая их конечные состояния."""
    if not isinstance(data, list):
        return []
    return [task for task in data
            if ((_get(_get(task, "metadata", {}), "task_domain") == "music_sync")
                or (not _get(task, "metadata") and _get(task, "provider_instance")))
            and (providers is None or task_provider(task) in providers)]


def _task_error(task):
    status = _get(task, "status")
    if status in ("pending", "running"):
        return None  # last_error может остаться от прошлого запуска
    error = _get(task, "last_error")
    if error:
        return str(error)
    if status in ("failed", "cancelled", "partial_success"):
        messages = _get(task, "failure_messages") or []
        return "; ".join(str(message) for message in messages) or f"Задача скана Music Assistant: {status}"
    if status not in ("pending", "running", "success"):
        return "Music Assistant вернул неизвестное состояние задачи скана"
    return None


async def _scan_progress(progress, tasks):
    if progress:
        active = [task for task in tasks if task_active(task)]
        value = progress({"stage": "scan", "tasks": len(active),
                          "providers": sorted({task_provider(task) for task in active if task_provider(task)})})
        if inspect.isawaitable(value):
            await value


def _supervisor_data(response):
    # HassIO.send_command возвращает весь JSON Supervisor, включая result/data.
    if not isinstance(response, dict) or response.get("result") == "error":
        raise ValueError("Supervisor не смог подготовить скан Music Assistant")
    data = response.get("data", response)
    if not isinstance(data, dict):
        raise ValueError("Supervisor вернул неверный ответ")
    return data


async def ingress_scan(hass, ha_user_id, providers, progress=None) -> dict:
    """Скан под пользователем HA через доверенную ingress-сессию Supervisor."""
    result = {"available": False, "scan_requested": False, "scheduled": True, "error": None}
    if not ha_user_id or not os.environ.get("SUPERVISOR"):
        return result
    # Импорт ленивый: обычная установка HA не обязана иметь Supervisor.
    from homeassistant.components.hassio.const import DATA_COMPONENT
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    if "hassio" not in hass.config.components or DATA_COMPONENT not in hass.data:
        return result
    supervisor = hass.data[DATA_COMPONENT]
    ws = None
    try:
        result["available"] = True
        async with asyncio.timeout(SCAN_TIMEOUT):
            slug = None
            for entry in hass.config_entries.async_entries("music_assistant"):
                hostname = urlsplit(entry.data.get("url", "")).hostname or ""
                candidate = hostname.replace("-", "_")
                if candidate.endswith("_music_assistant"):
                    slug = candidate
                    break
            if not slug:
                addons = _supervisor_data(await supervisor.send_command("/addons", method="get"))
                slug = next((_get(addon, "slug") for addon in addons.get("addons", [])
                             if str(_get(addon, "slug", "")).endswith("music_assistant")
                             and (_get(addon, "ingress") or _get(addon, "ingress_entry"))
                             and _get(addon, "state") == "started"), None)
            if not slug:
                result["available"] = False
                return result
            info = _supervisor_data(await supervisor.send_command(f"/addons/{slug}/info", method="get"))
            ingress_path = info.get("ingress_entry", "")
            if info.get("state") != "started" or not ingress_path.startswith("/api/hassio_ingress/"):
                result["available"] = False
                return result
            token = ingress_path.removeprefix("/api/hassio_ingress/").strip("/")
            if not token or "/" in token:
                raise ValueError("Supervisor вернул неверный путь ingress Music Assistant")
            if not providers:
                result["error"] = "Нет файловых источников Music Assistant"
                return result
            session_data = _supervisor_data(await supervisor.send_command(
                "/ingress/session", method="post", payload={"user_id": ha_user_id}))
            session = session_data.get("session")
            if not isinstance(session, str) or not session:
                raise ValueError("Supervisor не создал ingress-сессию Music Assistant")
            ws = await async_get_clientsession(hass).ws_connect(
                f"ws://{os.environ['SUPERVISOR']}/ingress/{token}/ws",
                headers={"Cookie": f"ingress_session={session}", "X-Hass-Source": "core.ingress",
                         "X-Ingress-Path": ingress_path})

            async def receive():
                message = await ws.receive()
                if message.type != aiohttp.WSMsgType.TEXT:
                    raise ConnectionError("Соединение скана Music Assistant закрыто")
                data = message.json()
                if not isinstance(data, dict):
                    raise ValueError("Music Assistant вернул неверный ответ скана")
                return data

            hello = await receive()  # MA авторизует ingress до чтения команд.
            if "error_code" in hello:
                if str(hello["error_code"]) in {"20", "21", "22", "23", "401", "403"}:
                    raise PermissionError(SCAN_AUTH_ERROR)
                raise ValueError(str(hello.get("details") or "Music Assistant отклонил соединение скана"))
            sequence = 0

            async def command(name, args):
                nonlocal sequence
                sequence += 1
                message_id = f"yandex_menu_scan_{sequence}"
                await ws.send_json({"message_id": message_id, "command": name, "args": args})
                partial = []
                while True:
                    data = await receive()
                    if data.get("message_id") not in (message_id, "connection"):
                        continue  # события и ответы других команд
                    if "error_code" in data:
                        code = str(data["error_code"])
                        if code in {"20", "21", "22", "23", "401", "403"}:
                            raise PermissionError(SCAN_AUTH_ERROR)
                        raise ValueError(str(data.get("details") or "Ошибка команды скана Music Assistant"))
                    if "result" not in data:
                        continue
                    value = data["result"]
                    if data.get("partial"):
                        if not isinstance(value, list):
                            raise ValueError("Music Assistant вернул неверный ответ скана")
                        partial.extend(value)
                        continue
                    return partial + value if partial and isinstance(value, list) else value

            tasks = await command("music/sync", {"media_types": ["track", "audiobook"],
                                                 "providers": list(providers)})
            result["scan_requested"] = True
            if not isinstance(tasks, list):
                raise ValueError("Music Assistant не вернул задачи скана")
            while True:
                for task in tasks:
                    if error := _task_error(task):
                        raise ValueError(error)
                    if not _get(task, "id"):
                        raise ValueError("Music Assistant вернул задачу скана без идентификатора")
                await _scan_progress(progress, tasks)
                active = [task for task in tasks if task_active(task)]
                if not active:
                    result["scheduled"] = False
                    return result
                await asyncio.sleep(SCAN_POLL_INTERVAL)
                # tasks/get проверяет именно запущенные задачи; пропавшая задача — ошибка,
                # а не свидетельство успешного завершения полного снимка библиотеки.
                updated = []
                for task in active:
                    task_id = _get(task, "id")
                    value = await command("tasks/get", {"task_id": task_id})
                    if _get(value, "id") != task_id:
                        raise ValueError("Music Assistant не подтвердил задачу скана")
                    updated.append(value)
                tasks = updated
    except TimeoutError:
        result["error"] = "Не удалось дождаться завершения скана Music Assistant"
    except aiohttp.WSServerHandshakeError as err:
        result["error"] = SCAN_AUTH_ERROR if err.status in (401, 403) else "Не удалось подключиться к скану Music Assistant"
    except aiohttp.ClientError:
        # В тексте aiohttp-ошибки бывает URL с секретным ingress-токеном.
        result["error"] = "Соединение скана Music Assistant недоступно"
    except Exception as err:
        result["error"] = str(err) or type(err).__name__
    finally:
        if ws is not None:
            await ws.close()
    return result


async def scan_library(mass, progress=None) -> dict:
    """Запросить скан и дождаться его событий, а не только ответа music/sync."""
    result = {"scan_requested": False, "scheduled": True, "error": None}
    if mass is None:
        result["error"] = "Music Assistant недоступен"
        return result
    unsubscribe = None
    try:
        providers = [_get(p, "instance_id") for p in _providers(mass)]
        if not providers:
            result["error"] = "Нет файловых источников Music Assistant"
            return result
        changed = asyncio.Event()
        tasks = None
        seen_running = False
        modern = False
        tracked = set()
        baseline = None
        watching = False

        def requested(data):
            return [task for task in scan_tasks(data, providers)
                    if not _get(task, "metadata")
                    or _get(_get(task, "metadata"), "media_type") in ("track", "audiobook")]

        def run_identity(task):
            return (_get(task, "last_run"), _get(task, "started_at"))

        def updated(event):
            nonlocal tasks, seen_running, modern
            data = _get(event, "data")
            if not watching or not isinstance(data, list):
                return
            tasks = requested(data)
            modern = _get(event, "event") == "tasks_updated" or any(_get(t, "metadata") for t in tasks)
            active = [task for task in tasks if task_active(task)]
            tracked.update(_get(task, "id") for task in active if _get(task, "id"))
            if baseline is not None:
                tracked.update(_get(task, "id") for task in tasks if _get(task, "id")
                               and (_get(task, "id") not in baseline
                                    or run_identity(task) != baseline[_get(task, "id")]))
            seen_running = seen_running or bool(active)
            changed.set()

        # Подписка до команды: короткий скан может закончиться раньше ответа.
        unsubscribe = mass.subscribe(updated, ("tasks_updated", "sync_tasks_updated"))
        async with asyncio.timeout(SCAN_TIMEOUT):
            if send_command := getattr(mass, "send_command", None):
                try:
                    previous = await send_command("tasks/list")
                except Exception as err:
                    if _get(err, "error_code") != 12:  # старый MA: InvalidCommand
                        raise
                else:
                    if not isinstance(previous, list):
                        raise ValueError("Music Assistant не вернул список задач скана")
                    # started_at/last_run отличают новый короткий запуск от истории;
                    # updated_at меняется также при редактировании расписания.
                    baseline = {_get(task, "id"): run_identity(task) for task in requested(previous)}
                    tracked.update(_get(task, "id") for task in requested(previous)
                                   if _get(task, "id") and task_active(task))
            watching = True
            await mass.music.start_sync(media_types=["track", "audiobook"], providers=providers)
            result["scan_requested"] = True
            while True:
                await changed.wait()
                changed.clear()
                await _scan_progress(progress, tasks)
                if modern and tracked:
                    current = {_get(task, "id"): task for task in tasks}
                    if tracked - current.keys():
                        raise ValueError("Music Assistant не подтвердил завершение задач скана")
                    for task_id in tracked:
                        if error := _task_error(current[task_id]):
                            raise ValueError(error)
                    if tracked and all(_get(current[task_id], "status") == "success" for task_id in tracked):
                        result["scheduled"] = False
                        return result
                elif seen_running and not tasks:
                    result["scheduled"] = False
                    return result
    except TimeoutError:
        result["error"] = "Не удалось дождаться завершения скана Music Assistant"
    except Exception as err:
        result["error"] = str(err) or type(err).__name__
    finally:
        if unsubscribe:
            unsubscribe()
    return result
