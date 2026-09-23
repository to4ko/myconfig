"""Тонкий клиент облака Яндекса (Квазар).

Авторизацию не заводим свою: берём готовую сессию интеграции yandex_station —
она сама держит куки, обновляет их и подставляет x-csrf-token.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .accounts import station_entries, station_entry
from .const import API, YS_DOMAIN

_LOGGER = logging.getLogger(__name__)


class QuasarError(Exception):
    """Ошибка, которую можно показать пользователю."""


class QuasarApi:
    """Запросы к iot.quasar.yandex.ru поверх сессии yandex_station."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    # ------------------------------------------------------------------ сессия

    @property
    def session(self):
        """Сессия выбранного аккаунта из yandex_station. Без неё работать не можем."""
        data = self.hass.data.get(YS_DOMAIN)
        entries = station_entries(self.hass)
        if not data or not entries:
            raise QuasarError(
                "Не найдена интеграция Яндекс.Станция — через неё берётся доступ к "
                "Яндекс-дому. Настройте её и перезапустите Home Assistant."
            )
        entry = station_entry(self.hass)
        if entry is None:
            raise QuasarError(
                "Аккаунт Яндекса, выбранный в настройках, больше не подключён. "
                "Выберите другой: Настройки → Устройства и службы → Яндекс меню → Настроить."
            )
        # Яндекс.Станция хранит аккаунты по логину — это unique_id записи
        session = getattr(data.get(entry.unique_id), "session", None)
        if session is None and len(entries) == 1:
            # Другая версия Станции могла сменить ключ; с одним аккаунтом ошибиться негде
            for value in data.values():
                session = getattr(value, "session", None)
                if session is not None:
                    break
        if session is not None:
            return session
        raise QuasarError(
            "Интеграция Яндекс.Станция есть, но её сессия не готова. "
            "Попробуйте перезагрузить интеграцию Яндекс.Станция."
        )

    async def _request(
        self, method: str, path: str, payload: dict | None = None
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if payload is not None:
            kwargs["json"] = payload
        try:
            response = await self.session.request(method, API + path, **kwargs)
            data = await response.json()
        except QuasarError:
            raise
        except Exception as err:  # noqa: BLE001 — показываем причину пользователю
            _LOGGER.debug("Ошибка запроса %s %s: %s", method, path, err)
            raise QuasarError(f"Яндекс не ответил: {err}") from err

        if data.get("status") != "ok":
            message = data.get("message") or data.get("code") or "неизвестная ошибка"
            raise QuasarError(message)
        return data

    # ------------------------------------------------------------------ чтение

    async def devices(self) -> dict[str, Any]:
        """Дома, их комнаты и устройства одним ответом.

        Старый /m/user/devices сваливает комнаты всех домов в один список и не
        говорит, где чья, поэтому берём v3 — там всё разложено по домам.
        """
        return await self._request("get", "/m/v3/user/devices")

    async def device_config(self, device_id: str) -> dict[str, Any]:
        """Карточка устройства: имена, комната, роль, привязанная сущность HA."""
        return await self._request("get", f"/m/user/devices/{device_id}/configuration")

    async def device(self, device_id: str) -> dict[str, Any]:
        """Умения устройства с названиями: цвета, режимы, диапазоны, датчики."""
        return await self._request("get", f"/m/user/devices/{device_id}")

    async def device_types(self, device_id: str) -> dict[str, Any]:
        """Типы и роли, доступные конкретному устройству."""
        return await self._request("get", f"/m/user/devices/{device_id}/types")

    async def rooms(self) -> list[dict[str, Any]]:
        data = await self._request("get", "/m/user/rooms")
        return data.get("rooms", [])

    async def scenarios(self) -> list[dict[str, Any]]:
        data = await self._request("get", "/m/user/scenarios")
        return data.get("scenarios", [])

    # ------------------------------------------------------------------- имена

    async def add_name(self, device_id: str, name: str) -> None:
        """Добавляет ещё одно голосовое имя. Отдельного «переименовать» в API нет."""
        await self._request("post", f"/m/user/devices/{device_id}/name", {"name": name})

    async def delete_name(self, device_id: str, name: str) -> None:
        await self._request(
            "delete", f"/m/user/devices/{device_id}/name", {"name": name}
        )

    async def make_primary(self, device_id: str, name: str) -> list[str]:
        """Поднимает имя в основные.

        Порядок имён в Яндексе — это порядок добавления, поменять его напрямую
        нельзя. Поэтому снимаем все остальные имена и добавляем их заново,
        уже после нужного. При сбое возвращаем исходный набор.
        """
        config = await self.device_config(device_id)
        names: list[str] = list(config.get("names") or [])
        if name not in names:
            raise QuasarError(f"У устройства нет имени «{name}».")
        if names[0] == name:
            return names

        others = [item for item in names if item != name]
        done: list[str] = []
        try:
            for item in others:
                await self.delete_name(device_id, item)
                done.append(item)
            for item in others:
                await self.add_name(device_id, item)
        except QuasarError:
            # пытаемся вернуть всё, что успели снять
            for item in done:
                try:
                    await self.add_name(device_id, item)
                except QuasarError:  # noqa: PERF203 — восстановление важнее скорости
                    _LOGGER.warning("Не удалось вернуть имя «%s»", item)
            raise
        return [name, *others]

    # ------------------------------------------------- комната, тип, удаление

    async def set_room(self, device_id: str, room_id: str) -> None:
        await self._request(
            "put", f"/m/user/devices/{device_id}/room", {"room": room_id}
        )

    async def set_type(self, device_id: str, device_type: str, role: str | None) -> None:
        payload: dict[str, Any] = {"type": device_type}
        if role:
            payload["role"] = role
        await self._request("put", f"/m/user/devices/{device_id}/type", payload)

    async def delete_device(self, device_id: str) -> None:
        await self._request("delete", f"/m/user/devices/{device_id}")

    async def discovery(self, skill_id: str) -> None:
        """«Обновить список устройств» — Яндекс перечитывает навык."""
        await self._request("post", f"/m/user/skills/{skill_id}/discovery")

    async def switch(self, device_id: str, value: bool) -> None:
        await self._request(
            "post",
            f"/m/user/devices/{device_id}/actions",
            {
                "actions": [
                    {
                        "type": "devices.capabilities.on_off",
                        "state": {"instance": "on", "value": value},
                    }
                ]
            },
        )

    async def blink(self, device_id: str, seconds: float = 3.0) -> None:
        """Включить и через несколько секунд выключить — проверка «то ли это»."""
        await self.switch(device_id, True)
        await asyncio.sleep(seconds)
        await self.switch(device_id, False)
