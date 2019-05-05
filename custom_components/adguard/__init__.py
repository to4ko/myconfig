"""Support for Adguard Home"""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_MONITORED_CONDITIONS, CONF_NAME, 
    CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME, CONF_SSL, CONF_VERIFY_SSL)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Adguard'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '80'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASS = 'password'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = False

MONITORED_CONDITIONS = {
    'blocked':
        ['Ads Blocked', 'ads', 'mdi:close-octagon-outline'],
    'blocked_percentage':
        ['Ads Percentage Blocked', '%', 'mdi:close-octagon-outline'],
    'queries':
        ['DNS Queries', 'queries', 'mdi:comment-question-outline'],
    'version':
        ['Version','', 'mdi:alpha-v-circle-outline'],
}

BINARY_SENSORS = {
    'protection_enabled',
    'querylog_enabled',
    'running',
}

DOMAIN = 'adguard'

CONFIG_SCHEMA = vol.Schema({
     DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASS): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,    
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,    
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,    
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=['queries']):
        vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
     })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """Load configuration for Adguard Home."""

    adguard_config = config[DOMAIN]

    from adguard.client import Client

    username = adguard_config.get(CONF_USERNAME)
    password = adguard_config.get(CONF_PASSWORD)
    host = adguard_config.get(CONF_HOST)
    use_tls = adguard_config.get(CONF_SSL)

    if (use_tls and adguard_config.get(CONF_PORT)==DEFAULT_PORT):
        port = '443'

    port = adguard_config.get(CONF_PORT)   
    verify_tls = adguard_config.get(CONF_VERIFY_SSL)
    
    session = async_get_clientsession(hass, verify_tls)
    loop = hass.loop
    client = Client(session, loop, host, port, username, password, ssl=use_tls)
    connection = await client.connection

    if not (connection['authenticated'] and connection['connected']):
        _LOGGER.error("Unable to setup Adguard Home")
        return False
    
    adguard_data = await client.general()
    await adguard_data.get_update()

    name = adguard_config.get(CONF_NAME)
    hass.data[DOMAIN] = {
      'name' : name, 
      'data': adguard_data
    }
    sensors = adguard_config[CONF_MONITORED_CONDITIONS]
    binary_sensors = BINARY_SENSORS
    
    hass.async_create_task(async_load_platform(
        hass, 'sensor', DOMAIN, sensors, config))
    
    hass.async_create_task(async_load_platform(
        hass, BINARY_SENSOR, DOMAIN, binary_sensors, config))
    
    async def enable_protection_handle(self):
        """Handle the enable protection service call."""

        await adguard_data.enable_protection()
        _LOGGER.info('Protection sensor will be updated diring next update cicle. Current protection status: %s', adguard_data.protection_enabled)
        
    async def disable_protection_handle(self):
        """Handle the enable protection service call."""

        await adguard_data.disable_protection()
        _LOGGER.info('Protection sensor will be updated diring next update cicle. Current protection status: %s', adguard_data.protection_enabled)
        
    hass.services.async_register(DOMAIN, 'enable_protection', enable_protection_handle)
    hass.services.async_register(DOMAIN, 'disable_protection', disable_protection_handle)    

    return True
