from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

class YandexWeather(Entity):
	entity_id = 'sensor.yandex_weather'
		
	def __init__(self, config):
		import requests
		
		self.__session = requests.Session()
		self.__session.headers.update({
			'X-Yandex-API-Key': config['api_key']
		})
		
		self.__point = {
			'lat': config['lat'],
			'lon': config['lon']
		}
		
		self.__attributes = {}
				
	async def async_added_to_hass(self):
		self.update()
		
	def __get(self, params):
		return self.__session.get('https://api.weather.yandex.ru/v1/informers', params=params)
		
	def __get_at(self, point):
		return self.__get(point).json()
		
	def update(self):
		self.__attributes = self.__get_at(self.__point)['fact']
	
	@property
	def name(self):
		return 'Yandex Weather'
	
	@property
	def state(self):
		return self.__attributes['temp']
	
	@property	
	def unit_of_measurement(self):
		return TEMP_CELSIUS
		
	@property
	def icon(self):
		return 'mdi:white-balance-sunny'
		
	@property
	def device_state_attributes(self):
		return self.__attributes

def setup_platform(hass, config, add_devices, discovery_info=None):
	add_devices([YandexWeather(config)])
