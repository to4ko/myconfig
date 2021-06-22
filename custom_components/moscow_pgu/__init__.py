__all__ = (
    "DOMAIN",
    "CONFIG_SCHEMA",
    "DEVICE_INFO_SCHEMA",
    "async_setup_entry",
    "async_setup",
    "async_authenticate_api_object",
    "async_unload_entry",
    "lazy_load_platforms_base_class",
)

import asyncio
import logging
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    TYPE_CHECKING,
    Type,
)

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from custom_components.moscow_pgu.api import (
    API,
    DEFAULT_APP_VERSION,
    DEFAULT_DEVICE_AGENT,
    DEFAULT_DEVICE_OS,
    DEFAULT_USER_AGENT,
    MoscowPGUException,
    Profile,
)
from custom_components.moscow_pgu.const import *
from custom_components.moscow_pgu.util import (
    async_authenticate_api_object,
    async_load_session,
    extract_config,
    find_existing_entry,
    generate_guid,
)

if TYPE_CHECKING:
    from custom_components.moscow_pgu._base import MoscowPGUEntity

_LOGGER = logging.getLogger(__name__)

DEVICE_INFO_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_APP_VERSION, default=DEFAULT_APP_VERSION): cv.string,
        vol.Optional(CONF_DEVICE_OS, default=DEFAULT_DEVICE_OS): cv.string,
        vol.Optional(CONF_DEVICE_AGENT, default=DEFAULT_DEVICE_AGENT): cv.string,
        vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): cv.string,
        vol.Optional(CONF_GUID, default=""): cv.string,
    }
)

FSSP_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FIRST_NAME): cv.string,
        vol.Required(CONF_LAST_NAME): cv.string,
        vol.Optional(CONF_MIDDLE_NAME): cv.string,
        vol.Required(CONF_BIRTH_DATE): cv.date,
    }
)

DRIVING_LICENSE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIES): cv.string,
        vol.Optional(CONF_ISSUE_DATE): cv.date,
    }
)


def lazy_load_platforms_base_class() -> Mapping[str, Type["MoscowPGUEntity"]]:
    return {
        platform: __import__(
            "custom_components.moscow_pgu." + platform, globals(), locals(), ("BASE_CLASS",)
        ).BASE_CLASS
        for platform in SUPPORTED_PLATFORMS
    }


NAME_FORMATS_SCHEMA: Optional[vol.Schema] = None


def _lazy_name_formats_schema(value: Mapping[str, Any]):
    global NAME_FORMATS_SCHEMA
    if NAME_FORMATS_SCHEMA is not None:
        return NAME_FORMATS_SCHEMA(value)

    platforms = lazy_load_platforms_base_class()
    NAME_FORMATS_SCHEMA = vol.Schema(
        {
            vol.Optional(cls.CONFIG_KEY, default=cls.DEFAULT_NAME_FORMAT): cv.string
            for base_cls in platforms.values()
            for cls in base_cls.__subclasses__()
        }
    )

    return NAME_FORMATS_SCHEMA(value)


SCAN_INTERVALS_SCHEMA: Optional[vol.Schema] = None


def _lazy_scan_intervals_schema(value: Any):
    global SCAN_INTERVALS_SCHEMA
    if SCAN_INTERVALS_SCHEMA is not None:
        return SCAN_INTERVALS_SCHEMA(value)

    platforms = lazy_load_platforms_base_class()
    mapping_schema_dict = {
        vol.Optional(cls.CONFIG_KEY, default=cls.DEFAULT_SCAN_INTERVAL): vol.All(
            cv.positive_time_period, vol.Clamp(min=cls.MIN_SCAN_INTERVAL)
        )
        for base_cls in platforms.values()
        for cls in base_cls.__subclasses__()
    }
    mapping_schema = vol.Schema(mapping_schema_dict)

    single_schema = vol.All(
        cv.positive_time_period,
        lambda x: dict.fromkeys(mapping_schema_dict.keys(), x),
        mapping_schema,
    )

    SCAN_INTERVALS_SCHEMA = vol.Any(single_schema, mapping_schema)

    return SCAN_INTERVALS_SCHEMA(value)


FILTER_SCHEMA: Optional[vol.Schema] = None


def _lazy_filter_schema(value: Any):
    global FILTER_SCHEMA
    if FILTER_SCHEMA is not None:
        return FILTER_SCHEMA(value)

    platforms = lazy_load_platforms_base_class()

    singular_validator = vol.Any(
        vol.All(vol.Any(vol.Equal(["*"]), vol.Equal(True)), lambda x: ["*"]),
        vol.All(vol.Any(vol.Equal([]), vol.Equal(False)), lambda x: []),
    )

    multiple_validator = vol.Any(
        vol.All(vol.Equal(True), lambda x: ["*"]),
        vol.All(vol.Equal(False), lambda x: []),
        vol.All(cv.ensure_list, [cv.string]),
    )

    FILTER_SCHEMA = vol.Schema(
        {
            vol.Optional(cls.CONFIG_KEY, default=lambda: ["*"]): (
                singular_validator if cls.SINGULAR_FILTER else multiple_validator
            )
            for base_cls in platforms.values()
            for cls in base_cls.__subclasses__()
        }
    )

    return FILTER_SCHEMA(value)


OPTIONAL_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_INFO, default=lambda: DEVICE_INFO_SCHEMA({})): DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_DRIVING_LICENSES, default=None): vol.All(
            cv.ensure_list,
            [vol.Optional(cv.string, lambda x: {CONF_NUMBER: x}), DRIVING_LICENSE_SCHEMA],
        ),
        vol.Optional(CONF_TRACK_FSSP_PROFILES, default=None): vol.All(
            cv.ensure_list, [FSSP_PROFILE_SCHEMA]
        ),
        vol.Optional(
            CONF_NAME_FORMAT, default=lambda: _lazy_name_formats_schema({})
        ): _lazy_name_formats_schema,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=lambda: _lazy_scan_intervals_schema({})
        ): _lazy_scan_intervals_schema,
        vol.Optional(CONF_FILTER, default=lambda: _lazy_filter_schema({})): _lazy_filter_schema,
        vol.Optional(CONF_TOKEN, default=None): vol.Any(vol.Equal(None), cv.string),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                OPTIONAL_ENTRY_SCHEMA.extend(
                    {
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                    },
                    extra=vol.PREVENT_EXTRA,
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    domain_config = config.get(DOMAIN)
    if not domain_config:
        return True

    domain_data = {}
    hass.data[DOMAIN] = domain_data

    yaml_config = {}
    hass.data[DATA_CONFIG] = yaml_config

    for user_cfg in domain_config:
        username = user_cfg[CONF_USERNAME]

        _LOGGER.debug('User "%s" entry from YAML', username)

        existing_entry = find_existing_entry(hass, username)
        if existing_entry:
            if existing_entry.source == SOURCE_IMPORT:
                yaml_config[username] = user_cfg
                _LOGGER.debug('Skipping existing import binding for "%s"', username)
            else:
                _LOGGER.warning(
                    "YAML config for user %s is overridden by another config entry!", username
                )
            continue

        yaml_config[username] = user_cfg
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_USERNAME: username}
            )
        )

    if yaml_config:
        _LOGGER.debug("YAML usernames: %s", '"' + '", "'.join(yaml_config.keys()) + '"')
    else:
        _LOGGER.debug("No configuration added from YAML")

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    username = config_entry.data[CONF_USERNAME]
    yaml_config = hass.data.get(DATA_CONFIG)

    if config_entry.source == SOURCE_IMPORT and not (yaml_config and username in yaml_config):
        _LOGGER.info(
            "Removing entry %s after removal from YAML configuration." % config_entry.entry_id
        )
        hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))
        return False

    config = extract_config(hass, config_entry)

    device_info = None

    if config_entry.options:
        device_info = config_entry.options.get(CONF_DEVICE_INFO)

    if device_info is None:
        device_info = config.get(CONF_DEVICE_INFO)
    else:
        device_info = DEVICE_INFO_SCHEMA(device_info)

    _LOGGER.debug('Setting up config entry for user "%s"' % username)

    from custom_components.moscow_pgu._base import MoscowPGUEntity

    password = config[CONF_PASSWORD]
    additional_args = {"cache_lifetime": MoscowPGUEntity.MIN_SCAN_INTERVAL.total_seconds()}

    if device_info:
        additional_args.update(
            {
                arg: device_info[conf]
                for arg, conf in {
                    "app_version": CONF_APP_VERSION,
                    "device_os": CONF_DEVICE_OS,
                    "device_agent": CONF_DEVICE_AGENT,
                    "user_agent": CONF_USER_AGENT,
                    "guid": CONF_GUID,
                }.items()
                if conf in device_info
            }
        )

    if not additional_args.get("guid"):
        # @TODO: this can be randomly generated?
        additional_args["guid"] = generate_guid(config)

    token = config_entry.options.get(CONF_TOKEN)
    if not token:
        token = config.get(CONF_TOKEN)

    if token:
        additional_args["token"] = token

    session_id = await async_load_session(hass, username)

    api_object = API(
        username=username,
        password=config[CONF_PASSWORD],
        session_id=session_id,
        **additional_args,
    )

    try:
        try:
            await api_object.init_session()
            await async_authenticate_api_object(hass, api_object)

        except MoscowPGUException as e:
            raise ConfigEntryNotReady("Error occurred while authenticating: %s", e)
    except BaseException:
        await api_object.close_session()
        raise

    hass.data.setdefault(DOMAIN, {})[username] = api_object
    hass.data.setdefault(DATA_ENTITIES, {})[config_entry.entry_id] = {}

    for platform in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    update_listener = config_entry.add_update_listener(async_reload_entry)
    hass.data.setdefault(DATA_UPDATE_LISTENERS, {})[config_entry.entry_id] = update_listener

    return True


async def async_reload_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
) -> None:
    """Reload Lkcomu InterRAO entry"""
    _LOGGER.info("Reloading configuration entry")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    username = config_entry.data[CONF_USERNAME]

    if DATA_CONFIG in hass.data and username in hass.data[DOMAIN]:
        # noinspection PyUnusedLocal
        api_object: API = hass.data[DOMAIN].pop(username)
        await api_object.close_session()

    if DATA_UPDATERS in hass.data and config_entry.entry_id in hass.data[DATA_UPDATERS]:
        updaters: Dict[str, Callable] = hass.data[DATA_UPDATERS].pop(config_entry.entry_id)
        for cancel_callback in updaters.values():
            cancel_callback()

    cancel_listener = hass.data[DATA_UPDATE_LISTENERS].pop(config_entry.entry_id)
    cancel_listener()

    await asyncio.gather(
        *(
            hass.config_entries.async_forward_entry_unload(config_entry, domain)
            for domain in SUPPORTED_PLATFORMS
        )
    )

    return True
