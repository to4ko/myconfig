import logging

from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, CONF_NAME, CONF_ICON
from homeassistant.helpers.entity import Entity

logger = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    try:
        if 'file' in config:
            finename = hass.config.path(config['file'])
            with open(finename, 'rt', encoding='utf-8') as f:
                source = f.read()
        elif 'source' in config:
            source = config['source']
        else:
            return
        code = compile(source, '<string>', 'exec')
        add_entities([PythonSensor(code, config)])

    except:
        logger.exception("Error init python script sensor")


class PythonSensor(Entity):
    _state = None

    def __init__(self, code, config: dict):
        self.code = code
        self.config = config
        self.attributes = {}

    async def async_added_to_hass(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        return self.config.get(CONF_NAME)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value

    @property
    def state_attributes(self):
        return self.attributes

    @property
    def unit_of_measurement(self):
        return self.config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def icon(self):
        return self.config.get(CONF_ICON)

    def update(self):
        try:
            exec(self.code)
        except:
            logger.exception(f"Error update {self.name}")
