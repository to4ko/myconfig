import logging
from collections import OrderedDict
from typing import Any, Dict, Mapping, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from custom_components.moscow_pgu import DEVICE_INFO_SCHEMA, DOMAIN, lazy_load_platforms_base_class
from custom_components.moscow_pgu.api import API, AuthenticationException, MoscowPGUException
from custom_components.moscow_pgu.const import CONF_DEVICE_INFO, CONF_FILTER, CONF_GUID
from custom_components.moscow_pgu.util import (
    async_authenticate_api_object,
    async_save_session,
    extract_config,
    generate_guid,
)


@config_entries.HANDLERS.register(DOMAIN)
class MoscowPGUConfigFlow(config_entries.ConfigFlow):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._user_schema: Optional[vol.Schema] = None
        self._entities_schema: Optional[vol.Schema] = None
        self._save_config: Optional[Dict[str, Any]] = None
        self._save_options: Optional[Dict[str, Any]] = None

    async def _check_entry_exists(self, username: str):
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            if config_entry.data.get(CONF_USERNAME) == username:
                return True

        return False

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._user_schema is None:
            self._user_schema = vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_DEVICE_INFO, default=False): cv.boolean,
                }
            )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self._user_schema)

        username = user_input[CONF_USERNAME]
        if await self._check_entry_exists(username):
            return self.async_abort(reason="already_exists")

        device_info_show = user_input.pop(CONF_DEVICE_INFO)
        self._save_config = {**user_input}

        if device_info_show:
            return await self.async_step_device_info()

        errors = await self._async_test_config()
        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self._user_schema, errors=errors
            )

        return await self.async_step_entities()

    async def async_step_device_info(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if user_input is None:
            return self.async_show_form(step_id="device_info", data_schema=DEVICE_INFO_SCHEMA)

        if not user_input.get(CONF_GUID):
            user_input[CONF_GUID] = generate_guid(self._save_config)

        self._save_config[CONF_DEVICE_INFO] = user_input

        errors = await self._async_test_config()
        if errors:
            return self.async_show_form(
                step_id="device_info", data_schema=DEVICE_INFO_SCHEMA, errors=errors
            )

        return await self.async_step_entities()

    async def async_step_entities(
        self,
        user_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._entities_schema is None:
            platforms = lazy_load_platforms_base_class()
            self._entities_schema = vol.Schema(
                {
                    vol.Optional(cls.CONFIG_KEY, default=True): cv.boolean
                    for base_cls in platforms.values()
                    for cls in base_cls.__subclasses__()
                }
            )

        if user_input is None:
            return self.async_show_form(
                step_id="entities",
                data_schema=self._entities_schema,
            )

        self._save_config[CONF_FILTER] = {
            key: ([] if value is False else ["*"]) for key, value in user_input.items()
        }

        errors = await self._async_test_config()
        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self._entities_schema, errors=errors
            )

        return await self._async_save_config()

    async def async_step_import(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if user_input is None:
            return self.async_abort(reason="empty_config")

        self._save_config = user_input

        return await self._async_save_config()

    def _create_api_object(self) -> API:
        arguments = {**self._save_config}

        if CONF_DEVICE_INFO in arguments:
            device_info = arguments.pop(CONF_DEVICE_INFO)
            arguments.update(device_info)

        arguments.pop(CONF_FILTER, None)

        return API(**arguments)

    async def _async_test_config(self) -> Optional[Dict[str, str]]:
        try:
            async with self._create_api_object() as api:
                await async_authenticate_api_object(self.hass, api)

        except AuthenticationException:
            return {"base": "invalid_credentials"}

        except MoscowPGUException:
            return {"base": "api_error"}

        else:
            await async_save_session(self.hass, api.username, api.session_id)

    async def _async_save_config(self):
        username = self._save_config[CONF_USERNAME]

        if await self._check_entry_exists(username):
            return self.async_abort(reason="already_exists")

        return self.async_create_entry(title=username, data=self._save_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MoscowPGUOptionsFlow(config_entry)


_LOGGER = logging.getLogger(__name__)


class MoscowPGUOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry):
        self.config_entry = config_entry
        self._filter_statuses: Optional[Mapping[str, bool]] = None

    async def async_step_init(self, user_input: Optional[ConfigType] = None) -> Dict[str, Any]:
        config_entry = self.config_entry
        if config_entry.source == config_entries.SOURCE_IMPORT:
            return self.async_abort(reason="yaml_not_supported")

        filter_statuses = self._filter_statuses
        if filter_statuses is None:
            platforms = lazy_load_platforms_base_class()
            filter_statuses = {
                entity_cls.CONFIG_KEY: entity_cls.SINGULAR_FILTER
                for platform_key, platform_cls in platforms.items()
                for entity_cls in platform_cls.__subclasses__()
            }
            self._filter_statuses = filter_statuses

        current_data = extract_config(self.hass, config_entry)

        errors = {}
        if user_input:
            filter_data = {}
            for key, is_singular in filter_statuses.items():
                if is_singular:
                    entities = []
                else:
                    entities = sorted(
                        set(
                            filter(
                                bool,
                                map(
                                    str.strip,
                                    user_input[key + "_list"].split(","),
                                ),
                            )
                        )
                    )

                    if "*" in entities:
                        errors[key + "_list"] = "asterisk_disallowed"

                if user_input[key]:
                    entities.append("*")

                filter_data[key] = entities

            current_data[CONF_FILTER] = filter_data

            if not errors:
                save_data = dict(current_data)
                del save_data[CONF_SCAN_INTERVAL]

                return self.async_create_entry(title="", data=save_data)

        else:
            filter_data = current_data[CONF_FILTER]

        schema_dict = OrderedDict()

        for config_key, is_singular in sorted(
            filter_statuses.items(), key=lambda x: (not x[1], x[0])
        ):
            list_data = list(filter_data.get(config_key, ["*"]))  # default value for new entities
            blacklist = "*" in list_data
            if blacklist:
                list_data.remove("*")

            schema_dict[vol.Optional(config_key, default=blacklist)] = cv.boolean
            if not is_singular:
                schema_dict[
                    vol.Optional(config_key + "_list", default=", ".join(list_data))
                ] = cv.string

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema_dict), errors=errors or None
        )
