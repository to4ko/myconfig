__all__ = (
    "make_common_async_setup_entry",
    "LkcomuInterRAOEntity",
    "async_refresh_api_data",
    "async_register_update_delegator",
    "UpdateDelegatorsDataType",
    "EntitiesDataType",
    "SupportedServicesType",
)

import asyncio
import logging
import re
from abc import abstractmethod
from datetime import timedelta
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Hashable,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Set,
    SupportsInt,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_DEFAULT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, StateType
from homeassistant.util import as_local, utcnow

from custom_components.lkcomu_interrao._util import (
    IS_IN_RUSSIA,
    async_get_icons_for_providers,
    mask_username,
    with_auto_auth,
)
from custom_components.lkcomu_interrao.const import (
    ATTRIBUTION_EN,
    ATTRIBUTION_RU,
    ATTR_ACCOUNT_CODE,
    ATTR_ACCOUNT_ID,
    CONF_ACCOUNTS,
    CONF_DEV_PRESENTATION,
    CONF_NAME_FORMAT,
    DATA_API_OBJECTS,
    DATA_ENTITIES,
    DATA_FINAL_CONFIG,
    DATA_PROVIDER_LOGOS,
    DATA_UPDATE_DELEGATORS,
    FORMAT_VAR_ACCOUNT_CODE,
    FORMAT_VAR_ACCOUNT_ID,
    FORMAT_VAR_CODE,
    FORMAT_VAR_ID,
    FORMAT_VAR_PROVIDER_CODE,
    FORMAT_VAR_PROVIDER_NAME,
    SUPPORTED_PLATFORMS,
)
from inter_rao_energosbyt.enums import ProviderType

if TYPE_CHECKING:
    from homeassistant.helpers.entity_registry import RegistryEntry
    from inter_rao_energosbyt.interfaces import Account, BaseEnergosbytAPI

_LOGGER = logging.getLogger(__name__)

_TLkcomuInterRAOEntity = TypeVar("_TLkcomuInterRAOEntity", bound="LkcomuInterRAOEntity")

AddEntitiesCallType = Callable[[List["MESEntity"], bool], Any]
UpdateDelegatorsDataType = Dict[str, Tuple[AddEntitiesCallType, Set[Type["MESEntity"]]]]
EntitiesDataType = Dict[Type["LkcomuInterRAOEntity"], Dict[Hashable, "LkcomuInterRAOEntity"]]


def make_common_async_setup_entry(
    entity_cls: Type["LkcomuInterRAOEntity"], *args: Type["LkcomuInterRAOEntity"]
):
    async def _async_setup_entry(
        hass: HomeAssistantType,
        config_entry: ConfigEntry,
        async_add_devices,
    ):
        current_entity_platform = entity_platform.current_platform.get()

        log_prefix = (
            f"[{config_entry.data[CONF_TYPE]}/{mask_username(config_entry.data[CONF_USERNAME])}]"
            f"[{current_entity_platform.domain}][setup] "
        )
        _LOGGER.debug(
            log_prefix
            + (
                "Регистрация делегата обновлений"
                if IS_IN_RUSSIA
                else "Registering update delegator"
            )
        )

        await async_register_update_delegator(
            hass,
            config_entry,
            current_entity_platform.domain,
            async_add_devices,
            entity_cls,
            *args,
        )

    _async_setup_entry.__name__ = "async_setup_entry"

    return _async_setup_entry


async def async_register_update_delegator(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    platform: str,
    async_add_entities: AddEntitiesCallType,
    entity_cls: Type["LkcomuInterRAOEntity"],
    *args: Type["LkcomuInterRAOEntity"],
    update_after_complete: bool = True,
):
    entry_id = config_entry.entry_id

    update_delegators: UpdateDelegatorsDataType = hass.data[DATA_UPDATE_DELEGATORS][entry_id]
    update_delegators[platform] = (async_add_entities, {entity_cls, *args})

    if update_after_complete:
        if len(update_delegators) != len(SUPPORTED_PLATFORMS):
            return

        await async_refresh_api_data(hass, config_entry)


DEV_CLASSES_PROCESSED = set()


async def async_refresh_api_data(hass: HomeAssistantType, config_entry: ConfigEntry):
    entry_id = config_entry.entry_id
    api: "BaseEnergosbytAPI" = hass.data[DATA_API_OBJECTS][entry_id]

    accounts = await with_auto_auth(api, api.async_update_accounts, with_related=False)

    update_delegators: UpdateDelegatorsDataType = hass.data[DATA_UPDATE_DELEGATORS][entry_id]

    log_prefix_base = (
        f"[{config_entry.data[CONF_TYPE]}/{mask_username(config_entry.data[CONF_USERNAME])}]"
    )
    refresh_log_prefix = log_prefix_base + "[refresh] "

    _LOGGER.info(
        refresh_log_prefix
        + (
            "Запуск обновления связанных с профилем данных"
            if IS_IN_RUSSIA
            else "Beginning profile-related data update"
        )
    )

    if not update_delegators:
        return

    try:
        provider_icons = await async_get_icons_for_providers(
            api, set(map(lambda x: x.provider_type, accounts.values()))
        )
    except BaseException as e:
        _LOGGER.warning(
            log_prefix_base
            + "[logos] "
            + (
                "Произошла ошибка при обновлении логотипов"
                if IS_IN_RUSSIA
                else "Error occurred while updating logos"
            )
            + ": "
            + repr(e)
        )
    else:
        if provider_icons:
            if DATA_PROVIDER_LOGOS in hass.data:
                hass.data[DATA_PROVIDER_LOGOS].update(provider_icons)
            else:
                hass.data[DATA_PROVIDER_LOGOS] = provider_icons

    entities: EntitiesDataType = hass.data[DATA_ENTITIES][entry_id]
    final_config: ConfigType = dict(hass.data[DATA_FINAL_CONFIG][entry_id])

    dev_presentation = final_config.get(CONF_DEV_PRESENTATION)
    dev_log_prefix = log_prefix_base + "[dev] "

    if dev_presentation:
        from pprint import pformat

        _LOGGER.debug(
            dev_log_prefix
            + ("Конечная конфигурация:" if IS_IN_RUSSIA else "Final configuration:")
            + "\n"
            + pformat(final_config)
        )

    platform_tasks = {}

    accounts_config = final_config.get(CONF_ACCOUNTS) or {}
    account_default_config = final_config[CONF_DEFAULT]

    for account_id, account in accounts.items():
        account_config = accounts_config.get(account.code)
        account_log_prefix_base = refresh_log_prefix + f"[{mask_username(account.code)}]"

        if account_config is None:
            account_config = account_default_config

        if account_config is False:
            continue

        for platform, (_, entity_classes) in update_delegators.items():
            platform_log_prefix_base = account_log_prefix_base + f"[{platform}]"
            add_update_tasks = platform_tasks.setdefault(platform, [])
            for entity_cls in entity_classes:
                cls_log_prefix_base = platform_log_prefix_base + f"[{entity_cls.__name__}]"
                if account_config[entity_cls.config_key] is False:
                    _LOGGER.debug(
                        log_prefix_base
                        + " "
                        + (
                            f"Лицевой счёт пропущен согласно фильтрации"
                            if IS_IN_RUSSIA
                            else f"Account skipped due to filtering"
                        )
                    )
                    continue

                if dev_presentation:
                    dev_key = (entity_cls, account.provider_type)
                    if dev_key in DEV_CLASSES_PROCESSED:
                        _LOGGER.debug(
                            cls_log_prefix_base
                            + "[dev] "
                            + (
                                f"Пропущен лицевой счёт ({mask_username(account.code)}) "
                                f"по уникальности типа"
                                if IS_IN_RUSSIA
                                else f"Account skipped ({mask_username(account.code)}) "
                                f"due to type uniqueness"
                            )
                        )
                        continue

                    DEV_CLASSES_PROCESSED.add(dev_key)

                current_entities = entities.setdefault(entity_cls, {})

                _LOGGER.debug(
                    cls_log_prefix_base
                    + "[update] "
                    + (
                        "Планирование процедуры обновления"
                        if IS_IN_RUSSIA
                        else "Planning update procedure"
                    )
                )

                add_update_tasks.append(
                    entity_cls.async_refresh_accounts(
                        current_entities,
                        account,
                        config_entry,
                        account_config,
                    )
                )

    if platform_tasks:

        async def _wrap_update_task(update_task):
            try:
                return await update_task
            except BaseException as task_exception:
                _LOGGER.exception(
                    f"Error occurred during task execution: {repr(task_exception)}",
                    exc_info=task_exception,
                )
                return None

        all_updates_count = sum(map(len, platform_tasks.values()))
        _LOGGER.info(
            refresh_log_prefix
            + (
                f"Выполнение процедур обновления ({all_updates_count}) для платформ: "
                f"{', '.join(platform_tasks.keys())}"
                if IS_IN_RUSSIA
                else f"Performing update procedures ({all_updates_count}) for platforms: "
                f"{', '.join(platform_tasks.keys())}"
            )
        )
        for platform, tasks in zip(
            platform_tasks.keys(),
            await asyncio.gather(
                *map(
                    lambda x: asyncio.gather(*map(_wrap_update_task, x)),
                    platform_tasks.values(),
                )
            ),
        ):
            all_new_entities = []
            for results in tasks:
                if results is None:
                    continue
                all_new_entities.extend(results)

            if all_new_entities:
                update_delegators[platform][0](all_new_entities, True)
    else:
        _LOGGER.warning(
            refresh_log_prefix
            + (
                "Отсутствуют подходящие платформы для конфигурации"
                if IS_IN_RUSSIA
                else "Missing suitable platforms for configuration"
            )
        )


class NameFormatDict(dict):
    def __missing__(self, key: str):
        if key.endswith("_upper") and key[:-6] in self:
            return str(self[key[:-6]]).upper()
        if key.endswith("_cap") and key[:-4] in self:
            return str(self[key[:-4]]).capitalize()
        if key.endswith("_title") and key[:-6] in self:
            return str(self[key[:-6]]).title()
        return "{{" + str(key) + "}}"


_TData = TypeVar("_TData")
_TAccount = TypeVar("_TAccount", bound="Account")


SupportedServicesType = Mapping[
    Optional[Tuple[type, SupportsInt]],
    Mapping[str, Union[dict, Callable[[dict], dict]]],
]


class LkcomuInterRAOEntity(Entity, Generic[_TAccount]):
    config_key: ClassVar[str] = NotImplemented

    _supported_services: ClassVar[SupportedServicesType] = {}

    def __init__(
        self,
        account: _TAccount,
        account_config: ConfigType,
    ) -> None:
        self._account: _TAccount = account
        self._account_config: ConfigType = account_config
        self._entity_updater = None

    def _handle_dev_presentation(
        self,
        mapping: MutableMapping[str, Any],
        filter_vars: Iterable[str],
        blackout_vars: Optional[Iterable[str]] = None,
    ) -> None:
        if self._account_config[CONF_DEV_PRESENTATION]:
            filter_vars = set(filter_vars)
            if blackout_vars is not None:
                blackout_vars = set(blackout_vars)
                filter_vars.difference_update(blackout_vars)

                for attr in blackout_vars:
                    value = mapping.get(attr)
                    if value is not None:
                        if isinstance(value, float):
                            value = "#####.###"
                        elif isinstance(value, int):
                            value = "#####"
                        elif isinstance(value, str):
                            value = "XXXXX"
                        else:
                            value = "*****"
                        mapping[attr] = value

            for attr in filter_vars:
                value = mapping.get(attr)
                if value is not None:
                    value = re.sub(r"[A-Za-z]", "X", str(value))
                    value = re.sub(r"[0-9]", "#", value)
                    value = re.sub(r"\w+", "*", value)
                    mapping[attr] = value

    #################################################################################
    # Config getter helpers
    #################################################################################

    @property
    def account_provider_code(self) -> Optional[str]:
        try:
            return ProviderType(self._account.provider_type).name.lower()
        except (ValueError, TypeError):
            return None

    @property
    def scan_interval(self) -> timedelta:
        return self._account_config[CONF_SCAN_INTERVAL][self.config_key]

    @property
    def name_format(self) -> str:
        return self._account_config[CONF_NAME_FORMAT][self.config_key]

    #################################################################################
    # Base overrides
    #################################################################################

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor"""

        attributes = {
            ATTR_ATTRIBUTION: (ATTRIBUTION_RU if IS_IN_RUSSIA else ATTRIBUTION_EN)
            % urlparse(self._account.api.BASE_URL).netloc,
            **(self.sensor_related_attributes or {}),
        }

        if ATTR_ACCOUNT_ID not in attributes:
            attributes[ATTR_ACCOUNT_ID] = self._account.id

        if ATTR_ACCOUNT_CODE not in attributes:
            attributes[ATTR_ACCOUNT_CODE] = self._account.code

        self._handle_dev_presentation(
            attributes,
            (ATTR_ACCOUNT_CODE, ATTR_ACCOUNT_ID),
        )

        return attributes

    @property
    def name(self) -> Optional[str]:
        name_format_values = {
            key: ("" if value is None else str(value))
            for key, value in self.name_format_values.items()
        }

        if FORMAT_VAR_CODE not in name_format_values:
            name_format_values[FORMAT_VAR_CODE] = self.code

        if FORMAT_VAR_ACCOUNT_CODE not in name_format_values:
            name_format_values[FORMAT_VAR_ACCOUNT_CODE] = self._account.code

        if FORMAT_VAR_ACCOUNT_ID not in name_format_values:
            name_format_values[FORMAT_VAR_ACCOUNT_ID] = str(self._account.id)

        if FORMAT_VAR_PROVIDER_CODE not in name_format_values:
            name_format_values[FORMAT_VAR_PROVIDER_CODE] = self.account_provider_code or "unknown"

        if FORMAT_VAR_PROVIDER_NAME not in name_format_values:
            name_format_values[FORMAT_VAR_PROVIDER_NAME] = self._account.provider_name

        self._handle_dev_presentation(
            name_format_values,
            (FORMAT_VAR_CODE, FORMAT_VAR_ACCOUNT_CODE),
            (FORMAT_VAR_ACCOUNT_ID, FORMAT_VAR_ID),
        )

        return self.name_format.format_map(NameFormatDict(name_format_values))

    #################################################################################
    # Hooks for adding entity to internal registry
    #################################################################################

    async def async_added_to_hass(self) -> None:
        _LOGGER.info(self.log_prefix + "Adding to HomeAssistant")
        self.updater_restart()

    async def async_will_remove_from_hass(self) -> None:
        _LOGGER.info(self.log_prefix + "Removing from HomeAssistant")
        self.updater_stop()

        registry_entry: Optional["RegistryEntry"] = self.registry_entry
        if registry_entry:
            entry_id: Optional[str] = registry_entry.config_entry_id
            if entry_id:
                data_entities: EntitiesDataType = self.hass.data[DATA_ENTITIES][entry_id]
                cls_entities = data_entities.get(self.__class__)
                if cls_entities:
                    remove_indices = []
                    for idx, entity in enumerate(cls_entities):
                        if self is entity:
                            remove_indices.append(idx)
                    for idx in remove_indices:
                        cls_entities.pop(idx)

    #################################################################################
    # Updater management API
    #################################################################################

    @property
    def log_prefix(self) -> str:
        return f"[{self.config_key}][{self.entity_id or '<no entity ID>'}] "

    def updater_stop(self) -> None:
        if self._entity_updater is not None:
            _LOGGER.debug(self.log_prefix + "Stopping updater")
            self._entity_updater()
            self._entity_updater = None

    def updater_restart(self) -> None:
        log_prefix = self.log_prefix
        scan_interval = self.scan_interval

        self.updater_stop()

        async def _update_entity(*_):
            nonlocal self
            _LOGGER.debug(log_prefix + f"Executing updater on interval")
            await self.async_update_ha_state(force_refresh=True)

        _LOGGER.debug(
            log_prefix + f"Starting updater "
            f"(interval: {scan_interval.total_seconds()} seconds, "
            f"next call: {as_local(utcnow()) + scan_interval})"
        )
        self._entity_updater = async_track_time_interval(
            self.hass,
            _update_entity,
            scan_interval,
        )

    async def updater_execute(self) -> None:
        self.updater_stop()
        try:
            await self.async_update_ha_state(force_refresh=True)
        finally:
            self.updater_restart()

    async def async_update(self) -> None:
        # @TODO: more sophisticated error handling
        await with_auto_auth(self._account.api, self.async_update_internal)

    #################################################################################
    # Functional base for inherent classes
    #################################################################################

    @classmethod
    @abstractmethod
    async def async_refresh_accounts(
        cls: Type[_TLkcomuInterRAOEntity],
        entities: Dict[Hashable, _TLkcomuInterRAOEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ) -> Optional[Iterable[_TLkcomuInterRAOEntity]]:
        raise NotImplementedError

    #################################################################################
    # Data-oriented base for inherent classes
    #################################################################################

    @abstractmethod
    async def async_update_internal(self) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def code(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def state(self) -> StateType:
        raise NotImplementedError

    @property
    @abstractmethod
    def icon(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def name_format_values(self) -> Mapping[str, Any]:
        raise NotImplementedError

    @property
    @abstractmethod
    def unique_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def device_class(self) -> Optional[str]:
        raise NotImplementedError

    def register_supported_services(self, for_object: Optional[Any] = None) -> None:
        for type_feature, services in self._supported_services.items():
            result, features = (
                (True, None)
                if type_feature is None
                else (isinstance(for_object, type_feature[0]), (int(type_feature[1]),))
            )

            if result:
                for service, schema in services.items():
                    self.platform.async_register_entity_service(
                        service, schema, "async_service_" + service, features
                    )
