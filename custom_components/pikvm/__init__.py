"""The PiKVM integration."""

import logging

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import UNDEFINED, ConfigType
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
    LEGACY_DOMAIN,
    MANUFACTURER,
)
from .coordinator import PiKVMDataUpdateCoordinator
from .utils import get_nested_value, normalize_serial

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type PiKVMConfigEntry = ConfigEntry[PiKVMDataUpdateCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)


def _extract_serial_from_entry_or_device(
    entry: ConfigEntry | None,
    dev_reg: dr.DeviceRegistry,
) -> str | None:
    """Extract normalized serial from a ConfigEntry or its associated devices."""
    if entry is not None:
        serial = normalize_serial(entry.data.get(CONF_SERIAL)) or normalize_serial(
            entry.unique_id
        )
        if serial:
            return serial
        for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            for domain, ident in dev.identifiers:
                if domain in (DOMAIN, LEGACY_DOMAIN) and (
                    norm_ident := normalize_serial(ident)
                ):
                    return norm_ident
    return None


def _migrate_entity_to_pikvm(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    entity_entry: er.RegistryEntry,
    new_entry_id: str,
    new_unique_id: str,
) -> None:
    """Safely migrate a single entity registry entry from pikvm_ha to pikvm."""
    if (
        entity_entry.platform == DOMAIN
        and entity_entry.config_entry_id == new_entry_id
        and entity_entry.unique_id == new_unique_id
    ):
        return

    if (
        state := hass.states.get(entity_entry.entity_id)
    ) is not None and state.state != STATE_UNKNOWN:
        hass.states.async_remove(entity_entry.entity_id)

    try:
        ent_reg.async_update_entity_platform(
            entity_entry.entity_id,
            DOMAIN,
            new_config_entry_id=new_entry_id,
            new_unique_id=(
                new_unique_id
                if new_unique_id != entity_entry.unique_id
                else UNDEFINED
            ),
        )
    except ValueError:
        ent_reg.async_update_entity(
            entity_entry.entity_id,
            new_unique_id=(
                new_unique_id
                if new_unique_id != entity_entry.unique_id
                else UNDEFINED
            ),
            config_entry_id=new_entry_id,
        )


def _cleanup_legacy_issues(hass: HomeAssistant, entry_id: str | None = None) -> None:
    """Remove stale Repairs issues left behind by pikvm_ha."""
    ir.async_delete_issue(hass, "homeassistant", f"integration_not_found.{LEGACY_DOMAIN}")
    if entry_id:
        ir.async_delete_issue(
            hass, "homeassistant", f"config_entry_reauth_{LEGACY_DOMAIN}_{entry_id}"
        )
        ir.async_delete_issue(hass, LEGACY_DOMAIN, f"undervoltage_{entry_id}")
        ir.async_delete_issue(hass, LEGACY_DOMAIN, f"throttling_{entry_id}")
        ir.async_delete_issue(hass, DOMAIN, f"undervoltage_{entry_id}")
        ir.async_delete_issue(hass, DOMAIN, f"throttling_{entry_id}")


async def _deduplicate_entry_into_primary(
    hass: HomeAssistant,
    dev_reg: dr.DeviceRegistry,
    ent_reg: er.EntityRegistry,
    primary_entry: ConfigEntry,
    dup_entry: ConfigEntry,
) -> None:
    """Merge devices and entities from dup_entry into primary_entry and remove dup_entry."""
    new_id = primary_entry.entry_id
    old_id = dup_entry.entry_id

    for dev in dr.async_entries_for_config_entry(dev_reg, old_id):
        new_identifiers = {
            (DOMAIN if dom == LEGACY_DOMAIN else dom, ident)
            for dom, ident in dev.identifiers
        }
        dev_reg.async_update_device(
            dev.id,
            add_config_entry_id=new_id,
            new_identifiers=new_identifiers,
        )

    for entity_entry in er.async_entries_for_config_entry(ent_reg, old_id):
        new_uid = entity_entry.unique_id
        if new_uid.startswith(f"{old_id}_"):
            new_uid = f"{new_id}_{new_uid[len(old_id) + 1:]}"
        _migrate_entity_to_pikvm(hass, ent_reg, entity_entry, new_id, new_uid)

    for dev in dr.async_entries_for_config_entry(dev_reg, old_id):
        dev_reg.async_update_device(dev.id, remove_config_entry_id=old_id)

    _cleanup_legacy_issues(hass, old_id)
    await hass.config_entries.async_remove(old_id)


async def async_migrate_legacy_domain(
    hass: HomeAssistant,
    target_entry: ConfigEntry | None = None,
) -> bool:
    """Seamlessly migrate legacy `pikvm_ha` config entries and deduplicate `pikvm` entries by serial."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    migrated_any = False

    legacy_entries = list(hass.config_entries.async_entries(LEGACY_DOMAIN))
    current_entries = list(hass.config_entries.async_entries(DOMAIN))
    if (
        target_entry is not None
        and target_entry not in current_entries
        and target_entry.domain == DOMAIN
    ):
        current_entries.append(target_entry)

    pikvm_by_serial: dict[str, ConfigEntry] = {}
    for entry in current_entries:
        serial = _extract_serial_from_entry_or_device(entry, dev_reg)
        if not serial:
            continue
        existing_primary = pikvm_by_serial.get(serial)
        if existing_primary is not None and existing_primary.entry_id != entry.entry_id:
            if target_entry is not None and entry.entry_id == target_entry.entry_id:
                primary_entry, dup_entry = entry, existing_primary
                pikvm_by_serial[serial] = primary_entry
            else:
                primary_entry, dup_entry = existing_primary, entry
            await _deduplicate_entry_into_primary(
                hass, dev_reg, ent_reg, primary_entry, dup_entry
            )
            migrated_any = True
        else:
            pikvm_by_serial[serial] = entry

    for legacy_entry in legacy_entries:
        serial = _extract_serial_from_entry_or_device(legacy_entry, dev_reg)
        matching_new_entry = pikvm_by_serial.get(serial) if serial else None

        if (
            matching_new_entry is not None
            and matching_new_entry.entry_id != legacy_entry.entry_id
        ):
            await _deduplicate_entry_into_primary(
                hass, dev_reg, ent_reg, matching_new_entry, legacy_entry
            )
            migrated_any = True
        else:
            entry_id = legacy_entry.entry_id

            for dev in dr.async_entries_for_config_entry(dev_reg, entry_id):
                new_identifiers = {
                    (DOMAIN if dom == LEGACY_DOMAIN else dom, ident)
                    for dom, ident in dev.identifiers
                }
                if new_identifiers != dev.identifiers:
                    dev_reg.async_update_device(dev.id, new_identifiers=new_identifiers)

            for entity_entry in er.async_entries_for_config_entry(ent_reg, entry_id):
                _migrate_entity_to_pikvm(
                    hass, ent_reg, entity_entry, entry_id, entity_entry.unique_id
                )

            entries_dict = getattr(hass.config_entries, "_entries", None)
            if entries_dict is not None and entry_id in entries_dict:
                del entries_dict[entry_id]
                object.__setattr__(legacy_entry, "domain", DOMAIN)
                object.__setattr__(legacy_entry, "_integration_for_domain", None)
                getattr(legacy_entry, "clear_state_cache", lambda: None)()
                getattr(legacy_entry, "clear_storage_cache", lambda: None)()
                entries_dict[entry_id] = legacy_entry
                getattr(hass.config_entries, "_async_schedule_save", lambda: None)()
                getattr(hass.config_entries, "async_update_issues", lambda: None)()

            _cleanup_legacy_issues(hass, entry_id)
            if serial:
                pikvm_by_serial[serial] = legacy_entry
            migrated_any = True

            if target_entry is None or target_entry.entry_id != entry_id:
                hass.async_create_task(hass.config_entries.async_setup(entry_id))

    for item in list(dev_reg.devices):
        device_entry = dev_reg.async_get(item) if isinstance(item, str) else item
        if device_entry is None:
            continue
        legacy_serials = [
            ident for dom, ident in device_entry.identifiers if dom == LEGACY_DOMAIN
        ]
        if not legacy_serials:
            continue
        serial = legacy_serials[0].strip().lower()
        matched_entry = pikvm_by_serial.get(serial) or target_entry
        new_identifiers = {
            (DOMAIN if dom == LEGACY_DOMAIN else dom, ident)
            for dom, ident in device_entry.identifiers
        }
        if matched_entry is not None:
            dev_reg.async_update_device(
                device_entry.id,
                add_config_entry_id=matched_entry.entry_id,
                new_identifiers=new_identifiers,
            )
            for entity_entry in er.async_entries_for_device(
                ent_reg, device_entry.id, include_disabled_entities=True
            ):
                if (
                    entity_entry.platform == LEGACY_DOMAIN
                    or entity_entry.config_entry_id != matched_entry.entry_id
                ):
                    old_cfg_id = entity_entry.config_entry_id or ""
                    new_uid = entity_entry.unique_id
                    if old_cfg_id and new_uid.startswith(f"{old_cfg_id}_"):
                        new_uid = (
                            f"{matched_entry.entry_id}_{new_uid[len(old_cfg_id) + 1:]}"
                        )
                    _migrate_entity_to_pikvm(
                        hass, ent_reg, entity_entry, matched_entry.entry_id, new_uid
                    )
        else:
            dev_reg.async_update_device(device_entry.id, new_identifiers=new_identifiers)
        migrated_any = True

    _cleanup_legacy_issues(hass)
    return migrated_any


async def async_migrate_entry(hass: HomeAssistant, config_entry: PiKVMConfigEntry) -> bool:
    """Migrate old config entry versions or legacy domain."""
    await async_migrate_legacy_domain(hass, target_entry=config_entry)
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PiKVM component."""
    await async_migrate_legacy_domain(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PiKVMConfigEntry) -> bool:
    """Set up PiKVM from a config entry."""
    await async_migrate_legacy_domain(hass, target_entry=entry)

    # Clean host for title disambiguation
    raw_host = entry.data.get(CONF_HOST, "")
    try:
        clean_host = parse_host_port(raw_host)[0]
    except Exception:  # noqa: BLE001
        clean_host = raw_host or "unknown"

    # Pre-emptively disambiguate generic entry titles before network I/O
    if entry.title in ("PiKVM", "pikvm", "localhost.localdomain", "", None):
        hass.config_entries.async_update_entry(entry, title="PiKVM")

    # Retrieve the unique ID and serial number safely from the config entry
    stored_serial = entry.data.get(CONF_SERIAL)
    unique_id = entry.unique_id
    effective_serial = stored_serial or unique_id or "unknown"

    # Check if the unique ID matches the stored serial number
    if stored_serial and unique_id != stored_serial:
        _LOGGER.debug("Updating unique ID from %s to %s", unique_id, stored_serial)
        hass.config_entries.async_update_entry(entry, unique_id=stored_serial)

    # Pre-emptively remove legacy mismatched devices and update device registry names
    # so offline and re-auth cards immediately display clean, disambiguated device names
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    expected_ident = (DOMAIN, effective_serial) if effective_serial != "unknown" else None

    for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        is_mismatched = expected_ident is not None and expected_ident not in dev.identifiers
        if is_mismatched:
            _LOGGER.info("Removing legacy mismatched PiKVM device: %s (%s)", dev.name, dev.id)
            for ent in er.async_entries_for_device(ent_reg, dev.id, include_disabled_entities=True):
                ent_reg.async_remove(ent.entity_id)
            dev_reg.async_remove_device(dev.id)
        elif dev.name_by_user is None and (
            dev.name in ("PiKVM", "pikvm", "localhost.localdomain", "", None)
            or (clean_host and dev.name and dev.name.endswith(f" ({clean_host})"))
            or (dev.name and dev.name.startswith("PiKVM ("))
        ):
            _LOGGER.info("Updating legacy device name for %s to %s", dev.id, entry.title)
            dev_reg.async_update_device(dev.id, name=entry.title)

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

    # Retrieve hardware and system information safely
    raw_data = getattr(coordinator.data, "raw", None)
    if not isinstance(raw_data, dict):
        raw_data = coordinator.data if isinstance(coordinator.data, dict) else {}

    platform = get_nested_value(raw_data, ["hw", "platform"], {})
    if not isinstance(platform, dict):
        platform = {}
    kvmd = get_nested_value(raw_data, ["system", "kvmd"], {})
    if not isinstance(kvmd, dict):
        kvmd = {}

    hw_info = getattr(coordinator.data, "hw", None)
    platform_info = getattr(hw_info, "platform", None)

    live_serial = normalize_serial(
        getattr(platform_info, "serial", None)
        or platform.get("serial")
        or getattr(coordinator.data, "serial", None)
    )
    if live_serial and effective_serial == "unknown":
        effective_serial = live_serial
        hass.config_entries.async_update_entry(
            entry,
            unique_id=effective_serial,
            data={**entry.data, CONF_SERIAL: effective_serial},
        )
        await async_migrate_legacy_domain(hass, target_entry=entry)

    model = (
        getattr(platform_info, "model", None)
        or getattr(platform_info, "type", None)
        or platform.get("model")
        or platform.get("type")
        or getattr(coordinator.data, "model", None)
    )
    hw_version = getattr(platform_info, "base", None) or platform.get("base")
    sw_version = getattr(coordinator.data, "kvmd_version", None) or kvmd.get("version")

    # If the entry has a custom title, honor it; otherwise disambiguate with discovered name or model
    discovered_name = getattr(coordinator.data, "name", None)
    host_suffix = f" ({clean_host})"
    has_legacy_host = bool(
        entry.title
        and (
            (clean_host and entry.title.endswith(host_suffix))
            or entry.title.startswith("PiKVM (")
            or (
                discovered_name
                and entry.title.startswith(f"{discovered_name} (")
                and entry.title.endswith(")")
            )
        )
    )

    if entry.title and not (
        has_legacy_host
        or entry.title in ("PiKVM", "pikvm", "localhost", "localhost.localdomain")
    ):
        device_name = entry.title
    elif discovered_name and discovered_name not in ("PiKVM", "pikvm", "localhost", "localhost.localdomain"):
        device_name = discovered_name
    elif model and model not in ("PiKVM", "pikvm"):
        device_name = f"PiKVM {model}"
    else:
        device_name = "PiKVM"

    if entry.title != device_name and (
        has_legacy_host
        or entry.title in ("PiKVM", "pikvm", "localhost", "localhost.localdomain", "", None)
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

    # Ensure device registry entry is in sync with latest device_name without deprecated async_get_device
    for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if dev.name_by_user is None and (
            dev.name != device_name
            or (clean_host and dev.name and dev.name.endswith(f" ({clean_host})"))
            or (dev.name and dev.name.startswith("PiKVM ("))
        ):
            dev_reg.async_update_device(dev.id, name=device_name)

    # Forward the setup to sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up orphaned devices that were created by previous versions
    await _async_cleanup_devices(hass, entry)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def _async_cleanup_devices(hass: HomeAssistant, entry: PiKVMConfigEntry) -> None:
    """Remove devices that do not belong to this config entry or have no entities."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    
    stored_serial = entry.data.get(CONF_SERIAL) or entry.unique_id
    expected_ident = (DOMAIN, stored_serial) if stored_serial else None

    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in devices:
        entities = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
        is_mismatched = expected_ident is not None and expected_ident not in device.identifiers
        if not entities or is_mismatched:
            _LOGGER.info("Removing stale or orphaned PiKVM device: %s (%s)", device.name, device.id)
            if is_mismatched:
                for ent in entities:
                    ent_reg.async_remove(ent.entity_id)
            dev_reg.async_remove_device(device.id)


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
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: PiKVMConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device if the device is stale."""
    device_identifiers = getattr(device_entry, "identifiers", None)
    if not device_identifiers:
        _LOGGER.info(
            "Allowing removal of PiKVM device %s (%s) with missing identifiers",
            getattr(device_entry, "name", None) or "Unknown",
            getattr(device_entry, "id", None) or "Unknown",
        )
        return True

    active_serial = config_entry.data.get(CONF_SERIAL) or config_entry.unique_id
    active_identifiers: set[tuple[str, str]] = set()

    if active_serial:
        raw_serial = str(active_serial).strip()
        norm_serial = raw_serial.lower()
        if raw_serial:
            active_identifiers.add((DOMAIN, raw_serial))
            active_identifiers.add((DOMAIN, norm_serial))
            active_identifiers.add((LEGACY_DOMAIN, raw_serial))
            active_identifiers.add((LEGACY_DOMAIN, norm_serial))

    coordinator = getattr(config_entry, "runtime_data", None)
    if (
        coordinator
        and getattr(coordinator, "device_info", None)
        and "identifiers" in coordinator.device_info
    ):
        active_identifiers.update(coordinator.device_info["identifiers"])

    raw_device_identifiers = (
        set(device_identifiers)
        if isinstance(device_identifiers, (set, list, tuple))
        else set()
    )

    normalized_active: set[tuple[str, str]] = {
        (str(d).strip().lower(), str(s).strip().lower())
        for d, s in active_identifiers
        if d and s
    }
    normalized_device: set[tuple[str, str]] = {
        (str(item[0]).strip().lower(), str(item[1]).strip().lower())
        for item in raw_device_identifiers
        if isinstance(item, tuple) and len(item) == 2 and item[0] and item[1]
    }

    if raw_device_identifiers.intersection(active_identifiers) or normalized_device.intersection(normalized_active):
        _LOGGER.warning(
            "Cannot remove active PiKVM device %s (%s)",
            getattr(device_entry, "name", None) or "Unknown",
            getattr(device_entry, "id", None) or "Unknown",
        )
        return False

    _LOGGER.info(
        "Allowing removal of stale PiKVM device %s (%s)",
        getattr(device_entry, "name", None) or "Unknown",
        getattr(device_entry, "id", None) or "Unknown",
    )
    return True