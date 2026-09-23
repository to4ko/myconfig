"""Интеграция «Яндекс меню»: своя панель в боковом меню Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from . import ws_api
from .accounts import account_key
from .const import (
    CONF_SHOW_IN_SIDEBAR,
    DATA_API,
    DATA_BUILD,
    DATA_CACHE,
    DATA_CACHE_OWNER,
    DATA_CACHE_STORE,
    DATA_CONFIGS,
    DATA_DETAILS,
    DATA_SAVED,
    DATA_SAVED_STORE,
    DATA_SNAPSHOTS,
    DATA_STORE,
    DATA_STORE_DATA,
    DATA_WS_REGISTERED,
    DOMAIN,
    PANEL_ICON,
    PANEL_JS,
    PANEL_STATIC_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
    CACHE_STORAGE_KEY,
    SAVED_STORAGE_KEY,
    STORAGE_KEY,
    STORAGE_VERSION,
    VERSION,
)
from .quasar_api import QuasarApi

_LOGGER = logging.getLogger(__name__)

DATA_PANEL_REGISTERED = "panel_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Поднимаем панель и WebSocket-команды."""
    data = hass.data.setdefault(DOMAIN, {})

    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load() or {}
    if "accounts" not in stored:
        # До выбора аккаунта слепки лежали одним списком — отдаём их текущему аккаунту
        stored = {"accounts": {account_key(hass): stored} if stored else {}}

    data[DATA_API] = QuasarApi(hass)
    data[DATA_STORE] = store
    data[DATA_STORE_DATA] = stored
    data[DATA_SNAPSHOTS] = stored["accounts"].setdefault(account_key(hass), {})
    data[DATA_CACHE] = None
    data[DATA_BUILD] = None
    await _async_load_devices(hass, data)

    # Хранилище списка одно на всё время работы HA. После перезагрузки записи
    # память свежее диска: отложенная запись могла ещё не дойти до файла.
    saved_store: Store | None = data.get(DATA_SAVED_STORE)
    if saved_store is None:
        saved_store = Store(hass, STORAGE_VERSION, SAVED_STORAGE_KEY)
        data[DATA_SAVED_STORE] = saved_store
        saved = await saved_store.async_load()
    else:
        saved = data.get(DATA_SAVED)
    # Список другого аккаунта не показываем: после смены аккаунта ждём свежий
    data[DATA_SAVED] = (
        saved if saved and saved.get("account") == account_key(hass) else None
    )

    if not data.get(DATA_WS_REGISTERED):
        ws_api.async_register(hass)
        data[DATA_WS_REGISTERED] = True

    await _async_register_panel(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_load_devices(hass: HomeAssistant, data: dict) -> None:
    """Настройки и карточки устройств — из памяти или с диска.

    Хранилище, как и список, одно на всё время работы HA: после перезагрузки
    записи (сменили настройки) память свежее диска. Чужой аккаунт — начинаем
    с пустого кэша.
    """
    owner = account_key(hass)
    store: Store | None = data.get(DATA_CACHE_STORE)
    if store is None:
        store = Store(hass, STORAGE_VERSION, CACHE_STORAGE_KEY)
        data[DATA_CACHE_STORE] = store
        stored = await store.async_load() or {}
        if isinstance(stored, dict) and stored.get("account") == owner:
            data[DATA_CONFIGS] = _entries(stored.get("configs"))
            data[DATA_DETAILS] = _entries(stored.get("details"))
            data[DATA_CACHE_OWNER] = owner
    if data.get(DATA_CACHE_OWNER) != owner:
        data[DATA_CONFIGS] = {}
        data[DATA_DETAILS] = {}
        data[DATA_CACHE_OWNER] = owner


def _entries(raw: object) -> dict[str, tuple[float, dict]]:
    """Записи кэша с диска; всё, что не похоже на «[когда, {…}]», пропускаем."""
    if not isinstance(raw, dict):
        return {}
    return {
        key: (float(value[0]), value[1])
        for key, value in raw.items()
        if isinstance(value, list | tuple)
        and len(value) == 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], dict)
    }


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Сменили настройки — перезапускаем: пункт меню, аккаунт и кэш берутся заново."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data[DOMAIN]
    if not data.get(DATA_PANEL_REGISTERED):
        panel_dir = Path(__file__).parent / "panel"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, str(panel_dir), False)]
        )
        data[DATA_PANEL_REGISTERED] = True

    # Без заголовка и значка панель не попадает в левое меню, но открывается по адресу
    in_sidebar = entry.options.get(CONF_SHOW_IN_SIDEBAR, True)
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE if in_sidebar else None,
        sidebar_icon=PANEL_ICON if in_sidebar else None,
        frontend_url_path=PANEL_URL_PATH,
        require_admin=True,
        config={
            "_panel_custom": {
                "name": "yandex-menu-panel",
                "module_url": f"{PANEL_STATIC_URL}/{PANEL_JS}?v={VERSION}",
                "embed_iframe": False,
                "trust_external": False,
                # Вырезы экрана панель обходит сама: шапка заходит под часы, а
                # карточка на телефоне открыта поверх всего экрана. HA до 2026.8
                # ключа не знает, но и отступов сам не делает — там работает то же.
                "handle_safe_area": True,
            }
        },
        update=True,
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Интеграцию удалили: сохранённый список больше некому показывать.

    Слепки остаются — вернёте интеграцию, и они снова пригодятся.
    """
    data = hass.data.get(DOMAIN, {})
    data[DATA_SAVED] = None
    ws_api._stop_build(hass)
    cache_store: Store = data.pop(DATA_CACHE_STORE, None) or Store(
        hass, STORAGE_VERSION, CACHE_STORAGE_KEY
    )
    await cache_store.async_remove()
    data.pop(DATA_CONFIGS, None)
    data.pop(DATA_DETAILS, None)
    data.pop(DATA_CACHE_OWNER, None)
    # Хранилище забираем: сборка, которая ещё идёт, его не найдёт и файл не
    # вернёт. А тот же экземпляр снимет и свою отложенную запись.
    store: Store = data.pop(DATA_SAVED_STORE, None) or Store(
        hass, STORAGE_VERSION, SAVED_STORAGE_KEY
    )
    await store.async_remove()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Убираем пункт из меню. Статический путь снять нельзя — он переживёт."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    ws_api._stop_build(hass)
    store: Store | None = hass.data.get(DOMAIN, {}).get(DATA_STORE)
    if store:
        await store.async_save(hass.data[DOMAIN][DATA_STORE_DATA])
    return True
