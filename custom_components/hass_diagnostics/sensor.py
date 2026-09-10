import asyncio
import logging
from datetime import timedelta
from typing import Iterable

from homeassistant import setup
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, UnitOfTime
from homeassistant.core import Event, HomeAssistant, ServiceCall

from .core.const import *
from .core.github import github_get_link
from .core.smart_log import convert_log_entry_to_record, parse_log_record


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    if config_entry.options.get(SMART_LOG, True):
        smart_log = SmartLog()

        # import log records from global system_log
        system_log = hass.data[SYSTEM_LOG]
        smart_log.emit_bulk(i.to_dict() for i in system_log.records.values())

        async def send_command(call: ServiceCall):
            smart_log.emit_bulk(call.data[SYSTEM_LOG])

        hass.services.async_register(DOMAIN, "send_command", send_command)

        async_add_entities([smart_log], False)

    if config_entry.options.get(START_TIME, True):
        async_add_entities([StartTime()], False)

    if config_entry.options.get(UNSAFE_STATE, True):
        async_add_entities([UnsafeState()], False)


class SmartLog(SensorEntity):
    _attr_icon = "mdi:math-log"
    _attr_name = "Smart Log"
    _attr_native_value = 0
    _attr_native_unit_of_measurement = "items"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unique_id = SMART_LOG
    _unrecorded_attributes = {"records"}

    def __init__(self):
        self.records: dict[tuple, dict] = {}

        handler = logging.Handler(logging.WARNING)
        handler.emit = self.emit
        logging.root.addHandler(handler)

    def emit(self, record: logging.LogRecord, count: int = 1):
        entry = parse_log_record(record)
        key = (
            entry.get("domain"),
            entry.get("package"),
            entry.get("category"),
            entry.get("host"),
        )
        if item := self.records.get(key):
            item["count"] += count
        else:
            entry["count"] = count
            if record.exc_text:
                entry["exception"] = record.exc_text
            if hasattr(record, "funcName"):
                entry["source"] = [
                    record.pathname,
                    record.lineno,
                    record.processName,
                    record.threadName,
                    record.funcName,
                ]
            else:
                entry["source"] = [record.pathname, record.lineno]
            if github := github_get_link(record):
                entry["github"] = github
            self.records[key] = entry

        self._attr_native_value += count
        if self.hass and self.entity_id:
            self.schedule_update_ha_state()

    def emit_bulk(self, entries: Iterable[dict]):
        for entry in entries:
            record = convert_log_entry_to_record(entry)
            self.emit(record, entry["count"])

    @property
    def extra_state_attributes(self):
        # fix JSON serialization
        return {"records": list(self.records.values())}


class StartTime(SensorEntity):
    _attr_icon = "mdi:home-assistant"
    _attr_name = "Start Time"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unique_id = START_TIME
    _unrecorded_attributes = {"setup_time"}

    def __init__(self):
        # hijack logger.info func because log level can be disabled
        logger = logging.getLogger("homeassistant.bootstrap")
        self.logger_info = logger.info
        logger.info = self.info

    def info(self, msg: str, *args):
        try:
            if msg == "Home Assistant initialized in %.2fs":
                self.internal_update(args[0])
        except:
            pass

        self.logger_info(msg, *args)

    def internal_update(self, state: float):
        if hasattr(setup, "async_get_setup_timings"):
            # Hass 2024.4+
            setup_time: dict[str, float] = setup.async_get_setup_timings(self.hass)
        else:
            setup_time: dict[str, float] = self.hass.data[SETUP_TIME]
            setup_time = setup_time.copy()  # protect original dict from changing

        for k, v in setup_time.items():
            if isinstance(v, float):  # Hass 2024.3+
                setup_time[k] = round(v, 2)
            elif isinstance(v, timedelta):  # before Hass 2024.3
                setup_time[k] = round(v.total_seconds(), 2)

        setup_time = dict(
            sorted(setup_time.items(), key=lambda kv: kv[1], reverse=True)
        )

        self._attr_extra_state_attributes = {SETUP_TIME: setup_time}
        self._attr_native_value = round(state, 2)
        self.schedule_update_ha_state()


class UnsafeState(SensorEntity):
    _attr_icon = "mdi:alert-circle"
    _attr_name = "Unsafe State"
    _attr_native_value = 0
    _attr_native_unit_of_measurement = "items"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unique_id = UNSAFE_STATE
    _unrecorded_attributes = {"events"}

    def __init__(self):
        self.events: list[dict] = []
        self._attr_extra_state_attributes = {"events": self.events}

    async def state_changed(self, event: Event):
        try:
            _ = asyncio.get_running_loop()
        except RuntimeError:
            if event.data not in self.events:
                self.events.append(event.data)
            self._attr_native_value += 1
            self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        remove = self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.state_changed)
        self.async_on_remove(remove)
