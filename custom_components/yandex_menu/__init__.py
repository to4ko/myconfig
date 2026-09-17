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
from .const import (
    CONF_SHOW_IN_SIDEBAR,
    DATA_API,
    DATA_CACHE,
    DATA_SNAPSHOTS,
    DATA_STORE,
    DATA_WS_REGISTERED,
    DOMAIN,
    PANEL_ICON,
    PANEL_JS,
    PANEL_STATIC_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
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
    snapshots = await store.async_load() or {}

    data[DATA_API] = QuasarApi(hass)
    data[DATA_STORE] = store
    data[DATA_SNAPSHOTS] = snapshots
    data[DATA_CACHE] = None

    if not data.get(DATA_WS_REGISTERED):
        ws_api.async_register(hass)
        data[DATA_WS_REGISTERED] = True

    await _async_register_panel(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Сменили настройки — перерегистрируем панель с пунктом меню или без."""
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
            }
        },
        update=True,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Убираем пункт из меню. Статический путь снять нельзя — он переживёт."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    store: Store | None = hass.data.get(DOMAIN, {}).get(DATA_STORE)
    if store:
        await store.async_save(hass.data[DOMAIN][DATA_SNAPSHOTS])
    return True
