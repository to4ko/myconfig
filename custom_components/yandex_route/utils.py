import logging
import re

from homeassistant.helpers.aiohttp_client import async_get_clientsession

RE_COORDS = re.compile(r'^[\d.,]+$')

_LOGGER = logging.getLogger(__name__)


class YandexRouter:
    def __init__(self, hass):
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.params = {
            'lang': 'ru',
            'locale': 'ru',
            'results': 1,
            'type': 'auto'
        }

    def state2coords(self, point: str):
        if RE_COORDS.search(point):
            return point

        state = self.hass.states.get(point)
        if state and 'latitude' in state.attributes and \
                'longitude' in state.attributes:
            return f"{state.attributes['longitude']}," \
                   f"{state.attributes['latitude']}"

        raise Exception(f"Can't get state {point}")

    async def build(self, points: list, params: dict):
        try:
            params['rll'] = '~'.join([self.state2coords(p) for p in points])

            for _ in range(2):
                # refresh token or build route
                r = await self.session.get(
                    'https://yandex.ru/maps/api/router/buildRoute',
                    params={**self.params, **params})

                data = await r.json()
                if 'csrfToken' in data:
                    self.params['csrfToken'] = data['csrfToken']
                    continue

                route = data['data']['routes'][0]
                return {
                    'duration': round(route.get('durationInTraffic',
                                                route['duration'])),
                    'distance': round(route['distance']['value']),
                    'text': route['distance']['text'],
                    'type': route['type']
                }

        except Exception as e:
            _LOGGER.error(f"Can't build route: {e}")

        return None
