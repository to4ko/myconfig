import asyncio
import datetime
import re
from datetime import timedelta
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Optional,
    Set,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
)

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.typing import HomeAssistantType

from custom_components.lkcomu_interrao.const import DOMAIN
from inter_rao_energosbyt.enums import ProviderType
from inter_rao_energosbyt.exceptions import EnergosbytException

if TYPE_CHECKING:
    from inter_rao_energosbyt.interfaces import BaseEnergosbytAPI


def _make_log_prefix(
    config_entry: Union[Any, ConfigEntry], domain: Union[Any, EntityPlatform], *args
):
    join_args = [
        (
            config_entry.entry_id[-6:]
            if isinstance(config_entry, ConfigEntry)
            else str(config_entry)
        ),
        (domain.domain if isinstance(domain, EntityPlatform) else str(domain)),
    ]
    if args:
        join_args.extend(map(str, args))

    return "[" + "][".join(join_args) + "] "


@callback
def _find_existing_entry(
    hass: HomeAssistantType, type_: str, username: str
) -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in existing_entries:
        if config_entry.data[CONF_TYPE] == type_ and config_entry.data[CONF_USERNAME] == username:
            return config_entry


def import_api_cls(type_: str) -> Type["BaseEnergosbytAPI"]:
    return __import__("inter_rao_energosbyt.api." + type_, globals(), locals(), ("API",)).API


_RE_USERNAME_MASK = re.compile(r"^(\W*)(.).*(.)$")


def mask_username(username: str):
    parts = username.split("@")
    return "@".join(map(lambda x: _RE_USERNAME_MASK.sub(r"\1\2***\3", x), parts))


_RE_FAVICON = re.compile(r'["\']?REACT_APP_FAVICON["\']?\s*:\s*"([\w.]+\.ico)"')

ICONS_FOR_PROVIDERS: Dict[str, Optional[Union[asyncio.Future, str]]] = {}


def _make_code_search_index(code):
    return tuple(map(str.lower, (code + "Logo", "defaultMarker" + code)))


async def async_get_icons_for_providers(
    api: "BaseEnergosbytAPI", provider_types: Set[int]
) -> Dict[str, str]:
    session = api._session
    base_url = api.BASE_URL
    icons = {}

    async with session.get(base_url + "/asset-manifest.json") as response:
        manifest = await response.json()

    iter_types = []

    for provider_type in provider_types:
        try:
            code = ProviderType(provider_type).name.lower()
        except (ValueError, TypeError):
            continue
        else:
            iter_types.append(code)

    for code in iter_types:
        search_index = _make_code_search_index(code)
        if "_" in code:
            root_code = code.split("_")[0]
            search_index = (*search_index, *_make_code_search_index(root_code))
        for key in manifest:
            lower_key = key.lower()
            for index_key in search_index:
                if index_key in lower_key:
                    icons[code] = base_url + "/" + manifest[key]
                    break

            if (
                code not in icons
                and code in key
                and (
                    lower_key.endswith(".png")
                    or lower_key.endswith(".jpg")
                    or lower_key.endswith(".svg")
                )
            ):
                icons[code] = base_url + "/" + manifest[key]

    # Diversion for ProviderType.TKO
    if ProviderType.TKO.name.lower() not in icons and ProviderType.MES.name.lower() in icons:
        icons[ProviderType.TKO.name.lower()] = icons[ProviderType.MES.name.lower()]

    if "main.js" in manifest:
        async with session.get(base_url + "/" + manifest["main.js"]) as response:
            js_code = await response.text()

        m = _RE_FAVICON.search(js_code)
        if m:
            url = base_url + "/" + m.group(1)
            for code in iter_types:
                icons.setdefault(code, url)

    return icons


LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

# Kaliningrad is excluded as it is not supported
IS_IN_RUSSIA = timedelta(hours=3) <= LOCAL_TIMEZONE.utcoffset(None) <= timedelta(hours=12)
_T = TypeVar("_T")
_RT = TypeVar("_RT")


async def with_auto_auth(
    api: "BaseEnergosbytAPI", async_getter: Callable[..., Coroutine[Any, Any, _RT]], *args, **kwargs
) -> _RT:
    try:
        return await async_getter(*args, **kwargs)
    except EnergosbytException:
        await api.async_authenticate()
        return await async_getter(*args, **kwargs)
