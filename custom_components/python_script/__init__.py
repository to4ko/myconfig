"""Component to allow running Python scripts.
https://docs.python.org/3/library/functions.html#compile
"""
import hashlib
import logging

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType, ServiceCallType
from homeassistant.requirements import async_process_requirements

_LOGGER = logging.getLogger(__name__)

DOMAIN = "python_script"
CONF_REQUIREMENTS = 'requirements'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_REQUIREMENTS): cv.ensure_list,
    })
}, extra=vol.ALLOW_EXTRA)


def md5(data: str):
    return hashlib.md5(data.encode()).hexdigest()


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    config: dict = hass_config[DOMAIN]
    if CONF_REQUIREMENTS in config:
        hass.async_create_task(async_process_requirements(
            hass, DOMAIN, config[CONF_REQUIREMENTS]
        ))

    cache_code = {}

    def handler(call: ServiceCallType):
        # Run with SyncWorker
        file = call.data.get('file')
        srcid = md5(call.data['source']) if 'source' in call.data else None
        cache = call.data.get('cache', True)

        if not (file or srcid):
            _LOGGER.error("Either file or source is required in params")
            return

        code = cache_code.get(file or srcid)

        if not cache or not code:
            if file:
                _LOGGER.debug("Load code from file")

                file = hass.config.path(file)
                with open(file, encoding='utf-8') as f:
                    code = compile(f.read(), file, 'exec')

                if cache:
                    cache_code[file] = code

            else:
                _LOGGER.debug("Load inline code")

                code = compile(call.data['source'], '<string>', 'exec')

                if cache:
                    cache_code[srcid] = code

        else:
            _LOGGER.debug("Load code from cache")

        execute_script(hass, call.data, _LOGGER, code)

    hass.services.async_register(DOMAIN, "exec", handler)

    return True


def execute_script(hass, data, logger, code):
    try:
        _LOGGER.debug("Run python script")
        exec(code)
    except Exception as e:
        _LOGGER.exception(f"Error executing script: {e}")
