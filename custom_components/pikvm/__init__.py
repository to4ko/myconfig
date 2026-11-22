"""The PiKVM integration."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from pikvm_aio import format_url, parse_host_port

from .const import (
    CONF_CERTIFICATE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SERIAL,
    CONF_TOTP,
    CONF_USERNAME,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import PiKVMDataUpdateCoordinator
from .utils import ensure_device_info, normalize_serial

__all__ = [
    "PLATFORMS",
    "PiKVMConfigEntry",
    "_async_cleanup_devices",
    "async_migrate_entry",
    "async_remove_config_entry_device",
    "async_remove_entry",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "resolve_device_name",
    "strip_legacy_host_suffix",
    "update_listener",
]

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type PiKVMConfigEntry = ConfigEntry[PiKVMDataUpdateCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)

_GENERIC_TITLES = ("PiKVM", "pikvm", "localhost", "localhost.localdomain", "", None)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: PiKVMConfigEntry
) -> bool:
    """Migrate old config entry versions."""
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PiKVM component."""
    return True


def strip_legacy_host_suffix(name: str | None, clean_host: str) -> str:
    """Strip legacy ' (<clean_host>)' suffix if present."""
    if not name:
        return ""
    host_suffix = f" ({clean_host})"
    if clean_host and name.endswith(host_suffix):
        cleaned = name[: -len(host_suffix)].strip()
        if cleaned:
            return cleaned
    return name


def resolve_device_name(
    entry_title: str | None,
    discovered_name: str | None,
    model: str | None,
    clean_host: str,
) -> tuple[str, bool]:
    """Determine (device_name, has_legacy_host) for entry title and DeviceInfo."""
    stripped_title = strip_legacy_host_suffix(entry_title, clean_host)
    has_legacy_host = bool(
        entry_title
        and (
            stripped_title != entry_title
            or entry_title.startswith("PiKVM (")
            or (
                discovered_name
                and entry_title.startswith(f"{discovered_name} (")
                and entry_title.endswith(")")
            )
        )
    )

    if entry_title and not (has_legacy_host or entry_title in _GENERIC_TITLES):
        device_name = entry_title
    elif discovered_name and discovered_name not in _GENERIC_TITLES:
        device_name = discovered_name
    elif model and model not in ("PiKVM", "pikvm"):
        device_name = f"PiKVM {model}"
    else:
        device_name = "PiKVM"
    return device_name, has_legacy_host


def _extract_device_metadata(
    data: object,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract normalized (live_serial, model, hw_version, sw_version) from coordinator data."""
    info = ensure_device_info(data)
    platform = info.hw.platform if info else None
    live_serial = normalize_serial(
        (platform.serial if platform else None) or getattr(data, "serial", None)
    )
    model = (
        (platform.model or platform.type if platform else None)
        or getattr(data, "model", None)
    ) or None
    hw_version = (platform.base if platform else None) or None
    sw_version = (info.kvmd_version if info else None) or getattr(
        data, "kvmd_version", None
    )
    return live_serial, model, hw_version, sw_version


async def async_setup_entry(hass: HomeAssistant, entry: PiKVMConfigEntry) -> bool:
    """Set up PiKVM from a config entry."""
    raw_host = entry.data.get(CONF_HOST, "")
    try:
        clean_host = parse_host_port(raw_host)[0]
    except Exception:  # noqa: BLE001
        clean_host = raw_host or "unknown"

    stored_serial = normalize_serial(entry.data.get(CONF_SERIAL))
    effective_serial = stored_serial or normalize_serial(entry.unique_id) or "unknown"

    if stored_serial and entry.unique_id != stored_serial:
        hass.config_entries.async_update_entry(entry, unique_id=stored_serial)

    coordinator = PiKVMDataUpdateCoordinator(
        hass,
        raw_host,
        entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
        entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD),
        entry.data.get(CONF_TOTP, ""),
        entry.data.get(CONF_CERTIFICATE, ""),
        entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    live_serial, model, hw_version, sw_version = _extract_device_metadata(
        coordinator.data
    )
    if live_serial and effective_serial == "unknown":
        effective_serial = live_serial
        hass.config_entries.async_update_entry(
            entry,
            unique_id=effective_serial,
            data={**entry.data, CONF_SERIAL: effective_serial},
        )

    discovered_name = getattr(coordinator.data, "name", None)
    device_name, has_legacy_host = resolve_device_name(
        entry.title, discovered_name, model, clean_host
    )

    if entry.title != device_name and (
        has_legacy_host or entry.title in _GENERIC_TITLES
    ):
        hass.config_entries.async_update_entry(entry, title=device_name)

    coordinator.device_info = DeviceInfo(
        identifiers={(DOMAIN, effective_serial)},
        configuration_url=format_url(raw_host),
        serial_number=effective_serial,
        manufacturer=MANUFACTURER,
        name=device_name,
        model=model,
        hw_version=hw_version,
        sw_version=sw_version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_cleanup_devices(hass, entry, device_name=device_name)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def _async_cleanup_devices(
    hass: HomeAssistant,
    entry: PiKVMConfigEntry,
    device_name: str | None = None,
) -> None:
    """Reconcile device registry: remove mismatched/orphaned devices and sync default name."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    stored_serial = normalize_serial(entry.data.get(CONF_SERIAL) or entry.unique_id)
    expected_ident = (DOMAIN, stored_serial) if stored_serial else None
    target_name = device_name or entry.title or "PiKVM"

    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        entities = er.async_entries_for_device(
            ent_reg, device.id, include_disabled_entities=True
        )
        is_mismatched = (
            expected_ident is not None and expected_ident not in device.identifiers
        )
        if not entities or is_mismatched:
            _LOGGER.info(
                "Removing stale or orphaned PiKVM device: %s (%s)",
                device.name,
                device.id,
            )
            for ent in entities:
                ent_reg.async_remove(ent.entity_id)
            dev_reg.async_remove_device(device.id)
        elif device.name_by_user is None and device.name != target_name:
            dev_reg.async_update_device(device.id, name=target_name)


async def async_unload_entry(hass: HomeAssistant, entry: PiKVMConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: PiKVMConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: PiKVMConfigEntry) -> None:
    """Handle removal of a config entry."""
    ir.async_delete_issue(hass, DOMAIN, f"undervoltage_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"throttling_{entry.entry_id}")


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: PiKVMConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device if the device is not the active device."""
    device_identifiers = getattr(device_entry, "identifiers", None)
    if not device_identifiers or not isinstance(device_identifiers, Iterable):
        return True

    active_serials: set[str] = set()
    if serial := normalize_serial(
        config_entry.data.get(CONF_SERIAL) or config_entry.unique_id
    ):
        active_serials.add(serial)

    coordinator = getattr(config_entry, "runtime_data", None)
    if (
        coordinator
        and coordinator.device_info
        and "identifiers" in coordinator.device_info
    ):
        for dom, ident in coordinator.device_info["identifiers"]:
            if dom == DOMAIN and (norm := normalize_serial(ident)):
                active_serials.add(norm)

    for item in device_identifiers:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and str(item[0]).strip().lower() == DOMAIN
            and normalize_serial(item[1]) in active_serials
        ):
            return False

    return True
