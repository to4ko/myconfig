import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import as_local, utcnow

from custom_components.moscow_pgu.api import API
from custom_components.moscow_pgu.const import CONF_FILTER, CONF_NAME_FORMAT, DATA_ENTITIES, DOMAIN
from custom_components.moscow_pgu.util import extract_config

_T = TypeVar("_T")

_LOGGER = logging.getLogger(__name__)


class NameFormatDict(dict):
    def __missing__(self, key):
        return "{" + str(key) + "}"


class MoscowPGUEntity(Entity):
    CONFIG_KEY: ClassVar[str] = NotImplemented
    DEFAULT_NAME_FORMAT: ClassVar[str] = NotImplemented
    DEFAULT_SCAN_INTERVAL: ClassVar[timedelta] = timedelta(hours=1)
    MIN_SCAN_INTERVAL: ClassVar[timedelta] = timedelta(seconds=30)
    SINGULAR_FILTER: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    async def async_refresh_entities(
        cls,
        hass: HomeAssistantType,
        async_add_entities: Callable[[List["MoscowPGUEntity"], bool], Any],
        config_entry: ConfigEntry,
        config: ConfigType,
        api: "API",
        leftover_entities: List["MoscowPGUEntity"],
        filter_entities: List[str],
        is_blacklist: bool,
    ) -> Iterable["MoscowPGUEntity"]:
        pass

    def __init__(
        self, name_format: Optional[str] = None, scan_interval: Optional[timedelta] = None
    ):
        self._entity_updater = None

        self.name_format = name_format
        self.scan_interval = scan_interval

    @property
    def scan_interval(self):
        return self._scan_interval

    @scan_interval.setter
    def scan_interval(self, value: Optional[Union[timedelta, int, float]]) -> None:
        if value is None:
            value = self.DEFAULT_SCAN_INTERVAL
        elif isinstance(value, (int, float)):
            value = timedelta(seconds=value)

        if value < self.MIN_SCAN_INTERVAL:
            _LOGGER.warning("Attempted to set scan interval lower than minimum")
            value = self.MIN_SCAN_INTERVAL

        self._scan_interval = value

    @property
    def name_format(self) -> str:
        return self._name_format

    @name_format.setter
    def name_format(self, value: Optional[str]) -> None:
        self._name_format = value or self.DEFAULT_NAME_FORMAT

    @property
    def log_prefix(self) -> str:
        entry_id = "?"
        registry_entry = self.registry_entry
        if registry_entry:
            config_entry_id = registry_entry.config_entry_id
            if config_entry_id:
                entry_id = config_entry_id[-6:]

        return "[%s][%s] " % (
            entry_id,
            self.unique_id,
        )

    #################################################################################
    # Updater handling
    #################################################################################

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

    @property
    def entity_updater(self):
        return self._entity_updater

    #################################################################################
    # HA-specific code
    #################################################################################

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        registry_entry = self.registry_entry
        if registry_entry is None:
            raise ValueError("added entity without registry entry")

        config_entry_id = registry_entry.config_entry_id
        if config_entry_id is None:
            raise ValueError("added entity without config registry entry")

        cls_entities = self.hass.data[DATA_ENTITIES][config_entry_id].setdefault(
            self.CONFIG_KEY, []
        )

        _LOGGER.debug("%sAdding to registry", self.log_prefix)
        cls_entities.append(self)

        # Start updater once everything is complete
        self.updater_restart()

    async def async_will_remove_from_hass(self) -> None:
        # Stop updater firstmost
        _LOGGER.debug("%sWill remove from registry", self.log_prefix)
        self.updater_stop()

        registry_entry = self.registry_entry
        if registry_entry:

            config_entry_id = registry_entry.config_entry_id
            if config_entry_id:
                cls_entities = self.hass.data[DATA_ENTITIES][config_entry_id].get(self.CONFIG_KEY)

                if cls_entities and self in cls_entities:
                    cls_entities.remove(self)

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        _device_state_attributes = self.sensor_related_attributes or {}
        _device_state_attributes.setdefault(ATTR_ATTRIBUTION, "Data provided by Moscow PGU")

        if "api" in _device_state_attributes:
            del _device_state_attributes["api"]

        if ATTR_DEVICE_CLASS not in _device_state_attributes:
            device_class = self.device_class
            if device_class is not None:
                _device_state_attributes[ATTR_DEVICE_CLASS] = device_class

        return _device_state_attributes

    @property
    def sensor_related_attributes(self) -> Optional[Dict[str, Any]]:
        return None

    @property
    def name(self) -> Optional[str]:
        name_format_values = NameFormatDict(
            {
                key: ("" if value is None else value)
                for key, value in self.name_format_values.items()
            }
        )
        return self.name_format.format_map(name_format_values)

    @property
    def unique_id(self) -> str:
        raise NotImplementedError

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        raise NotImplementedError

    async def async_update(self) -> None:
        raise NotImplementedError


class MoscowPGUCollectiveUpdateEntity(MoscowPGUEntity, ABC):
    """Base class for entities that receive their updates from single request.

    This ensures that same request will be re-used.
    """

    _collective_update_future: ClassVar[Optional[asyncio.Future]] = None

    @abstractmethod
    async def async_get_collective_update_data(self):
        pass

    @abstractmethod
    async def async_update_from_collective_data(self, collective_data):
        pass

    @abstractmethod
    async def async_update(self) -> None:
        cls = self.__class__

        collective_update_future = cls._collective_update_future
        if collective_update_future:
            # Update requests that fall within a 5-second threshold
            # will wait for cumulative result
            collective_data = await collective_update_future

        else:
            collective_update_future = self.hass.loop.create_future()
            cls._collective_update_future = collective_update_future

            try:
                # Let other update requests appear
                await asyncio.sleep(5)

                # Next update requests will have to perform a separate request
                cls._collective_update_future = None

                # Fetch collective data
                collective_data = await self.async_get_collective_update_data()

            except BaseException as e:
                # Send exception to those awaiting collective data
                collective_update_future.set_exception(e)
                raise

            else:
                # Send update result to those awaiting collective data
                collective_update_future.set_result(collective_data)

        # Just a check that the entity is still there when an update happens
        if self._added:

            # Perform post-collective update
            await self.async_update_from_collective_data(collective_data)


TSensor = TypeVar("TSensor", bound="MoscowPGUEntity")


def make_platform_setup(*entity_classes: Type[MoscowPGUEntity]):
    async def async_setup_entry(
        hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
    ):
        config = extract_config(hass, config_entry)
        username = config[CONF_USERNAME]

        # Prepare necessary arguments
        api: API = hass.data[DOMAIN][username]
        all_existing_entities: Dict[str, List[MoscowPGUEntity]] = hass.data[DATA_ENTITIES][
            config_entry.entry_id
        ]

        update_cls = []
        update_tasks = []
        leftover_map = {}
        for entity_cls in entity_classes:
            config_key = entity_cls.CONFIG_KEY
            entity_cls_filter = config[CONF_FILTER][config_key]
            if not entity_cls_filter:
                # Effectively means entity is disabled
                _LOGGER.debug(f'Entities `{config_key}` are disabled for user "{username}"')
                continue

            leftover_entities = list(all_existing_entities.setdefault(config_key, []))
            leftover_map[entity_cls] = leftover_entities
            is_blacklist = "*" in entity_cls_filter
            update_cls.append(entity_cls)

            update_tasks.append(
                entity_cls.async_refresh_entities(
                    hass,
                    async_add_entities,
                    config_entry,
                    config,
                    api,
                    leftover_entities,
                    entity_cls_filter,
                    is_blacklist,
                )
            )

        new_entities = []
        tasks = []

        for entity_cls, results in zip(update_cls, await asyncio.gather(*update_tasks)):
            if isinstance(results, BaseException):
                _LOGGER.error("Exception: %s", exc_info=results)
            else:
                name_format = config[CONF_NAME_FORMAT][entity_cls.CONFIG_KEY]
                scan_interval = config[CONF_SCAN_INTERVAL][entity_cls.CONFIG_KEY]

                for result in results:
                    result.name_format = name_format
                    result.scan_interval = scan_interval
                    new_entities.append(result)

                existing_entities = all_existing_entities[entity_cls.CONFIG_KEY]
                leftover_entities = leftover_map[entity_cls]

                for entity in existing_entities:
                    if entity in leftover_entities:
                        tasks.append(hass.async_create_task(entity.async_remove()))
                    else:
                        entity.name_format = name_format
                        needs_updater_update = (
                            entity.entity_updater and entity.scan_interval != scan_interval
                        )
                        entity.scan_interval = scan_interval
                        if needs_updater_update:
                            entity.updater_restart()

        if tasks:
            await asyncio.wait(tasks)

        _LOGGER.debug(f'Finished component setup for user "{username}"')

    return async_setup_entry


def dt_to_str(dt: Optional[Union[date, time, datetime]]) -> Optional[str]:
    """Optional date to string helper"""
    if dt is not None:
        return dt.isoformat()


def iter_and_add_or_update(
    ent_cls: Type[_T],
    async_add_entities: Callable[[List[_T], bool], Any],
    leftover_entities: List[_T],
    objs: Iterable[Any],
    ent_attr: str,
    cmp_attrs: Optional[Tuple[str, ...]] = None,
    check_none: bool = True,
    refresh_after: bool = False,
    checker: Callable[[Iterable[bool]], bool] = all,
    **kwargs,
) -> List[_T]:
    if isinstance(cmp_attrs, str):
        cmp_attrs = (cmp_attrs,)

    entities = []

    for obj in objs:
        if (
            check_none
            and cmp_attrs
            and any(getattr(obj, cmp_attr, None) is None for cmp_attr in cmp_attrs)
        ):
            continue

        entity = None

        for existing_entity in leftover_entities:
            existing_entity_obj = getattr(existing_entity, ent_attr)
            if existing_entity_obj is None:
                continue

            if not cmp_attrs or checker(
                getattr(existing_entity_obj, cmp_attr) == getattr(obj, cmp_attr)
                for cmp_attr in cmp_attrs
            ):
                entity = existing_entity
                break

        kwargs[ent_attr] = obj

        if entity is None:
            entities.append(ent_cls(**kwargs))

        else:
            leftover_entities.remove(entity)
            if entity.enabled:
                for key, value in kwargs.items():
                    setattr(entity, key, value)
                entity.async_schedule_update_ha_state(force_refresh=refresh_after)

    if entities:
        async_add_entities(entities, refresh_after)

    return entities
