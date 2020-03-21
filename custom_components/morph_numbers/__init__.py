from homeassistant.helpers import template

from . import utils

DOMAIN = 'morphy2'


# noinspection PyUnusedLocal
def setup(hass, hass_config):
    _TemplateEnvironment = template.TemplateEnvironment

    def monkey(*args):
        env = _TemplateEnvironment(*args)
        env.filters['numword'] = utils.numword
        return env

    template.TemplateEnvironment = monkey
    # noinspection PyProtectedMember
    template._NO_HASS_ENV.filters['numword'] = utils.numword

    return True
