"""Support for Yeelink Light."""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import *

from . import (
    YeelightEntity,
    MiotLightEntity,
    DOMAIN,
    CONF_MODEL,
    PLATFORM_SCHEMA,
    XIAOMI_MIIO_SERVICE_SCHEMA,
    bind_services_to_entries,
)

_LOGGER = logging.getLogger(__name__)
DATA_KEY = f'light.{DOMAIN}'

SERVICE_SCHEMA_SET_SCENE = XIAOMI_MIIO_SERVICE_SCHEMA.extend(
    {
        vol.Optional('scene', default=0): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=8)),
        vol.Optional('params'): list,
    },
)

SERVICE_SCHEMA_SET_DELAYED_TURN_OFF = XIAOMI_MIIO_SERVICE_SCHEMA.extend(
    {
        vol.Required('time_period'): cv.positive_time_period,
        vol.Optional('power', default=False): cv.boolean,
    }
)

SERVICE_TO_METHOD = {
    'light_set_scene': {
        'method': 'async_set_scene',
        'schema': SERVICE_SCHEMA_SET_SCENE,
    },
    'light_set_delayed_turn_off': {
        'method': 'async_set_delayed_turn_off',
        'schema': SERVICE_SCHEMA_SET_DELAYED_TURN_OFF,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, config_entry.data)
    await async_setup_platform(hass, config, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}
    host = config[CONF_HOST]
    model = config.get(CONF_MODEL)
    entities = []
    if model.find('light.fancl') > 0:
        entity = MiotLightEntity(config)
        entities.append(entity)
    else:
        entity = YeelightEntity(config)
        entities.append(entity)
    for entity in entities:
        hass.data[DOMAIN]['entities'][entity.unique_id] = entity
    async_add_entities(entities, update_before_add=True)
    bind_services_to_entries(hass, SERVICE_TO_METHOD)
