"""Support for Yeelink Fan and Bath heater."""
import logging
import voluptuous as vol

from homeassistant.const import *

from . import (
    BathHeaterEntity,
    BathHeaterEntityV5,
    VenFanEntity,
    MiotFanEntity,
    DOMAIN,
    CONF_MODEL,
    PLATFORM_SCHEMA,
    bind_services_to_entries,
)

_LOGGER = logging.getLogger(__name__)
DATA_KEY = f'fan.{DOMAIN}'

SERVICE_TO_METHOD = {}


async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, config_entry.data)
    await async_setup_platform(hass, config, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}
    host = config[CONF_HOST]
    name = config[CONF_NAME]
    mode = config.get(CONF_MODE)
    model = config.get(CONF_MODEL)
    entities = []
    if model in ['yeelink.bhf_light.v1', 'yeelink.bhf_light.v2']:
        cfg = config.copy()
        prt = None
        for m in ['warmwind', 'venting', 'drying', 'drying_cloth', 'coolwind']:
            cfg.update({CONF_NAME: f'{name} {m}'})
            entity = BathHeaterEntity(cfg, m, prt)
            if prt is None:
                prt = entity
            entities.append(entity)
    elif model in ['yeelink.bhf_light.v5', 'yeelink.bhf_light.v6']:
        cfg = config.copy()
        prt = None
        for m in ['warmwind', 'venting', 'drying', 'coolwind', 'fastwarm', 'fastdefog']:
            cfg.update({CONF_NAME: f'{name} {m}'})
            entity = BathHeaterEntityV5(cfg, m, prt)
            if prt is None:
                prt = entity
            entities.append(entity)
    elif model.find('light.fancl') > 0:
        entity = MiotFanEntity(config)
        entities.append(entity)
    elif mode:
        entity = BathHeaterEntity(config, mode)
        entities.append(entity)
    else:
        entity = VenFanEntity(config)
        entities.append(entity)
    for entity in entities:
        hass.data[DOMAIN]['entities'][entity.unique_id] = entity
    async_add_entities(entities, update_before_add=True)
    bind_services_to_entries(hass, SERVICE_TO_METHOD)
