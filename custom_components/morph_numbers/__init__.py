from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import TemplateEnvironment
from jinja2.filters import do_format

from .utils import MorphNumber

DOMAIN = "morph_numbers"

MORPH = MorphNumber()


# noinspection PyUnusedLocal
async def async_setup(hass, hass_config):
    if DOMAIN in hass_config and not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )
    return True


# noinspection PyUnusedLocal
async def async_setup_entry(hass: HomeAssistant, entry):
    for env in hass.data.values():
        if isinstance(env, TemplateEnvironment):
            env.filters["format"] = morph_format

    # noinspection PyTypeChecker
    init_wrapper.orig = TemplateEnvironment.__init__
    TemplateEnvironment.__init__ = init_wrapper

    return True


# noinspection PyUnusedLocal
async def async_unload_entry(hass, entry):
    for env in hass.data.values():
        if isinstance(env, TemplateEnvironment):
            env.filters["format"] = do_format

    # noinspection PyUnresolvedReferences
    TemplateEnvironment.__init__ = init_wrapper.orig

    return True


# use an existing filter so as not to get an initialization error
def morph_format(value, *args, **kwargs):
    if "morph" in kwargs:
        if kwargs.get("as_ordinal"):
            return MORPH.number_to_ordinal(value, kwargs["morph"])

        if kwargs.get("reverse"):
            return MORPH.text_to_integer(value)

        as_text = kwargs.get("as_text", True)

        if isinstance(kwargs["morph"], list):
            return MORPH.number_with_custom_text(value, kwargs["morph"], as_text)

        return MORPH.number_with_text(value, kwargs["morph"], as_text)

    else:
        return do_format(value, *args, **kwargs)


def init_wrapper(*args, **kwargs):
    # noinspection PyUnresolvedReferences
    init_wrapper.orig(*args, **kwargs)
    args[0].filters["format"] = morph_format
