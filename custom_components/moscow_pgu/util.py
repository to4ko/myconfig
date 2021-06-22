import asyncio
import hashlib
import json
import logging
import os
from typing import Callable, Dict, Hashable, Mapping, MutableMapping, Optional, Tuple, TypeVar

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from custom_components.moscow_pgu.const import DATA_SESSION_LOCK
from custom_components.moscow_pgu.api import API, MoscowPGUException
from custom_components.moscow_pgu import Profile

from custom_components.moscow_pgu.const import DATA_CONFIG, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_lock(hass: HomeAssistantType):
    session_lock = hass.data.get(DATA_SESSION_LOCK)
    if session_lock is None:
        session_lock = asyncio.Lock()
        hass.data[DATA_SESSION_LOCK] = session_lock
    return session_lock


def read_sessions_file(hass: HomeAssistantType) -> Tuple[Dict[str, str], str]:
    filename = hass.config.path(os.path.join(".storage", DOMAIN + ".sessions"))
    contents = {}
    if os.path.isfile(filename):
        with open(filename, "rt") as f:
            try:
                contents = json.load(f)
            except json.JSONDecodeError:
                pass
    return contents, filename


async def async_load_session(hass: HomeAssistantType, username: str) -> Optional[str]:
    def load_session_from_json() -> Optional[str]:
        contents, _ = read_sessions_file(hass)
        return contents.get(username)

    async with async_get_lock(hass):
        return load_session_from_json()


async def async_save_session(hass: HomeAssistantType, username: str, session_id: str) -> None:
    def save_session_to_json() -> None:
        contents, filename = read_sessions_file(hass)
        contents[username] = session_id
        with open(filename, "w") as f:
            json.dump(contents, f)

    async with async_get_lock(hass):
        save_session_to_json()


async def async_authenticate_api_object(
    hass: HomeAssistantType,
    api: API,
    skip_session: bool = False,
) -> Profile:
    username = api.username
    if api.session_id is None or skip_session:
        _LOGGER.debug('Authenticating with user "%s"', username)

        await api.authenticate()

        _LOGGER.debug('Authentication successful for user "%s"', username)

        await async_save_session(hass, username, api.session_id)

        _LOGGER.debug('Saved session for user "%s"', username)

    else:
        _LOGGER.debug('Loaded session for user "%s"', username)

    try:
        return await api.get_profile()
    except MoscowPGUException as e:
        _LOGGER.exception("ERROR DURING PROFILE %s", e)
        if not skip_session:
            return await async_authenticate_api_object(hass, api, True)
        raise


TMutableMapping = TypeVar("TMutableMapping", bound=MutableMapping)


def recursive_mapping_update(
    d: TMutableMapping, u: Mapping, filter_: Optional[Callable[[Hashable], bool]] = None
) -> TMutableMapping:
    """
    Recursive mutable mapping updates.
    Borrowed from: https://stackoverflow.com/a/3233356
    :param d: Target mapping (mutable)
    :param u: Source mapping (any)
    :param filter_: (optional) Filter keys (`True` result carries keys from target to source)
    :return: Target mapping (mutable)
    """
    for k, v in u.items():
        if not (filter_ is None or filter_(k)):
            continue
        if isinstance(v, Mapping):
            d[k] = recursive_mapping_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def generate_guid(config: ConfigType):
    hash_str = "homeassistant&" + config[CONF_USERNAME] + "&" + config[CONF_PASSWORD]
    return hashlib.md5(hash_str.encode("utf-8")).hexdigest().lower()


def extract_config(hass: HomeAssistantType, config_entry: ConfigEntry):
    """
    Exctact configuration for integration.
    :param hass: Home Assistant object
    :param config_entry: Configuration entry
    :return: Configuration dictionary
    """
    from custom_components.moscow_pgu import OPTIONAL_ENTRY_SCHEMA

    username = config_entry.data[CONF_USERNAME]

    if config_entry.source == SOURCE_IMPORT:
        return {**hass.data[DATA_CONFIG][username]}

    config = OPTIONAL_ENTRY_SCHEMA({**config_entry.data})

    if config_entry.options:
        options = OPTIONAL_ENTRY_SCHEMA({**config_entry.options})
        recursive_mapping_update(
            config,
            {
                key: value
                for key, value in options.items()
                if key not in (CONF_USERNAME, CONF_PASSWORD)
            },
        )

    return config


@callback
def find_existing_entry(hass: HomeAssistantType, username: str) -> Optional[ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in existing_entries:
        if config_entry.data[CONF_USERNAME] == username:
            return config_entry
