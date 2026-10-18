"""Немедленно сохраняем голосовые запуски отдельно для каждого аккаунта."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from homeassistant.helpers.storage import Store


class VoiceStore:
    def __init__(self, hass, account):
        self.hass = hass
        self.store = Store(hass, 1, "yandex_menu.voice_launches")
        self.account = account
        self.data = {"accounts": {}}
        self.lock = asyncio.Lock()

    async def load(self):
        self.data = await self.store.async_load() or {"accounts": {}}
        return self.data.setdefault("accounts", {}).setdefault(
            self.account, {"launches": {}, "excluded": [], "speaker_map": {}}
        )

    async def save(self):
        async with self.lock:
            # Отмена вызывающей задачи не останавливает уже начатый executor HA.
            # Держим замок до его фактического завершения: unload ждёт эту задачу,
            # и следующий владелец не прочитает/не перезапишет Store раньше неё.
            write = self.hass.async_create_task(
                self.store.async_save(deepcopy(self.data)),
                "Яндекс меню: сохранение голосовых запусков",
            )
            cancelled = False
            while True:
                try:
                    await asyncio.shield(write)
                    break
                except asyncio.CancelledError:
                    if write.cancelled():
                        raise
                    # Повторная отмена также не освобождает замок раньше потока.
                    cancelled = True
            if cancelled:
                raise asyncio.CancelledError
