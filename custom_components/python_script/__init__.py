import hashlib
import logging
import traceback

import voluptuous as vol
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import JSON_DUMP
from homeassistant.helpers.typing import ConfigType
from homeassistant.requirements import async_process_requirements

_LOGGER = logging.getLogger(__name__)

DOMAIN = "python_script"
CONF_REQUIREMENTS = "requirements"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_REQUIREMENTS): cv.ensure_list,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("file"): str,
        vol.Optional("source"): str,
        vol.Optional("cache"): bool,
    },
    extra=vol.ALLOW_EXTRA,
)


def md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


async def async_setup(hass: HomeAssistant, hass_config: ConfigType):
    config: dict = hass_config.get(DOMAIN) or {}
    if CONF_REQUIREMENTS in config:
        hass.async_create_task(
            async_process_requirements(hass, DOMAIN, config[CONF_REQUIREMENTS])
        )

    cache_code = {}

    def handler(call: ServiceCall) -> ServiceResponse:
        # Run with SyncWorker
        file = call.data.get("file")
        srcid = md5(call.data["source"]) if "source" in call.data else None
        cache = call.data.get("cache", True)

        if not (file or srcid):
            _LOGGER.error("Either file or source is required in params")
            return

        code = cache_code.get(file or srcid)

        if not cache or not code:
            if file:
                _LOGGER.debug("Load code from file")

                file = hass.config.path(file)
                with open(file, encoding="utf-8") as f:
                    code = compile(f.read(), file, "exec")

                if cache:
                    cache_code[file] = code

            else:
                _LOGGER.debug("Load inline code")

                code = compile(call.data["source"], "<string>", "exec")

                if cache:
                    cache_code[srcid] = code

        else:
            _LOGGER.debug("Load code from cache")

        return execute_script(hass, call.data, call.context, _LOGGER, code)

    hass.services.async_register(
        DOMAIN,
        "exec",
        handler,
        SERVICE_SCHEMA,
        SupportsResponse.OPTIONAL,
    )

    return True


def execute_script(hass, data, context, logger, code) -> ServiceResponse:
    try:
        _LOGGER.debug("Run python script")
        vars = {**globals(), **locals()}
        exec(code, vars)
        response = {
            k: v for k, v in vars.items() if k not in globals() and simple_type(v)
        }
        return response
    except Exception as e:
        _LOGGER.error(f"Error executing script", exc_info=e)
        return {"error": str(e), "traceback": "".join(traceback.format_exception(e))}


def simple_type(value) -> bool:
    """Can be converted to JSON."""
    # https://github.com/AlexxIT/PythonScriptsPro/issues/26
    if value is None or isinstance(value, (str, int, float, bool)):
        return True

    if isinstance(value, (dict, list)):
        try:
            return JSON_DUMP(value) is not None
        except TypeError:
            pass

    return False


def compile_script(hass: HomeAssistant, config: dict):
    try:
        if "file" in config:
            filename = hass.config.path(config["file"])
            with open(filename, "rt", encoding="utf-8") as f:
                return compile(f.read(), filename, "exec")

        if "source" in config:
            return compile(config["source"], "<string>", "exec")

    except Exception as e:
        _LOGGER.error("Error init python script sensor", exc_info=e)


class PythonEntity(Entity):
    def __init__(self, code, config: dict):
        self.code = code
        self.config = config

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_extra_state_attributes = {}
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config.get(CONF_NAME)
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)

    @property
    def attributes(self):
        return self._attr_extra_state_attributes

    @attributes.setter
    def attributes(self, value):
        self._attr_extra_state_attributes = value

    def update(self):
        try:
            exec(self.code)
        except Exception as e:
            _LOGGER.error(f"Error update {self.name}", exc_info=e)
