"""Platform for sensor integration."""
import logging
from datetime import datetime
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mosportal'
DEFAULT_NAME = 'Счетчик воды  (Моспортал)'
CONF_METER_ID = 'meter_id'


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]

    meter_list = discovery_info.items()
    if not meter_list:
        return

    entities = []
    for meter in meter_list:
        sensor = WaterSensor(
            client,
            meter[0],
            meter[1]
        )
        entities.append(sensor)
    _LOGGER.debug(f'Счетчики моспортала добавлены {entities}')

    async_add_entities(entities,update_before_add=True)


class WaterSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, client, meter_id, name):
        """Initialize the sensor."""
        self._state = None
        self.client = client
        self.meter_id = meter_id
        self._name = name
        self.update_time = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state:
            return self._state.value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'м³'

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"mosportal_{self.name}"

    @property
    def device_state_attributes(self):
        if self._state:
            attributes = {
                'counterId': self._state.counterId,
                'meter_id': self._state.meter_id,
                'checkup': self._state.checkup,
                'consumption': self._state.consumption,
                'history_list': self._state.history_list,
                'refresh_date': self.update_time,
            }
            return attributes

    async def async_update(self):
        self._state, self.update_time = await self.async_fetch_state()

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_fetch_state(self):
        try:
            meter_list = await self.client.fetch_data()

            if not meter_list:
                return

            for item in meter_list.values():
                if item.meter_id == self.meter_id:
                    return item, datetime.now()
        except BaseException:
            _LOGGER.exception('ошибка получения состояния счетчиков с портала')
