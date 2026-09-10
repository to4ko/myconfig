from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from .core.const import SETUP_TIME, SYSTEM_LOG
from .sensor import SmartLog, StartTime


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    info = {}

    # global system_log
    if system_log := hass.data[SYSTEM_LOG]:
        info[SYSTEM_LOG] = [i.to_dict() for i in system_log.records.values()]

    component: EntityComponent = hass.data["entity_components"]["sensor"]
    for entity in component.entities:
        if isinstance(entity, SmartLog):
            info[entity.unique_id] = [i for i in entity.records.values()]
        if isinstance(entity, StartTime):
            info[entity.unique_id] = entity.native_value
            if entity.extra_state_attributes:
                info[SETUP_TIME] = entity.extra_state_attributes[SETUP_TIME]

    return info
