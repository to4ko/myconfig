import logging
import json
from mosportal import Epd, Water, Session, WaterException, EpdNotExist
from .const import DOMAIN, CONF_PAYCODE, CONF_FLAT, FLAT_LIST
import async_timeout
from datetime import datetime
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
import base64
from os.path import join, dirname, abspath
import pkg_resources


_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(FLAT_LIST): vol.All(
                    cv.ensure_list, [vol.Schema(
                        {
                            vol.Required(CONF_PAYCODE): cv.string,
                            vol.Required(CONF_FLAT): cv.string
                        }
                    )]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, base_config: dict):
    _LOGGER.info(
        'Используется версия модуля mosportal: %s' %
        pkg_resources.get_distribution("mosportal").version)
    config = base_config[DOMAIN]
    _LOGGER.debug("настройка компонента моспортал")

    client = PortalWrap(
        hass,
        Session(
            str(config[CONF_USERNAME]),
            str(config[CONF_PASSWORD]),
            cookie_save_path=join(
                dirname(abspath(__file__)), '..', '..', '.storage')
        ),
        config[FLAT_LIST]
    )

    hass.data[DOMAIN] = client

    meter_list = await client.fetch_data()

    if meter_list:
        _LOGGER.debug("счетчики получены")
        hass.async_create_task(
            async_load_platform(
                hass,
                SENSOR_DOMAIN,
                DOMAIN,
                discovered={
                    meter.meter_id: meter.name for meter in meter_list.values()},
                hass_config=config,
            )
        )
    else:
       _LOGGER.warning("информация о счетчиках воды на портале Москвы не найдена") 

    async def trigger_get_epd_service(call):
        try:
            month = call.data.get('month', datetime.now().month)
            year = call.data.get('year', datetime.now().year)
            data = call.data.get('data', {})
            payload = call.data.get('payload', None)

            await hass.async_add_executor_job(
                client.get_epd_service, month, year, data, payload
            )

        except BaseException as e:
            _LOGGER.exception(f'ошибка постановки задачи {e}')
            _LOGGER.debug(f'данные для задачи {call.data}')

    async def publish_water_usage(call):
        try:
            if 'meter_list_to_update' not in call.data:
                _LOGGER.error('переданы не корректные данные на вход в сервис')
                return

            meter_list_to_update = {
                item['meter_id']: item for item in call.data['meter_list_to_update']
            }
            await hass.async_add_executor_job(
                client.publish_water_usage, meter_list_to_update
            )

        except BaseException as e:
            _LOGGER.exception(f'ошибка постановки задачи {e}')

    hass.services.async_register(DOMAIN, 'get_epd', trigger_get_epd_service)
    hass.services.async_register(
        DOMAIN, 'publish_water_usage', publish_water_usage)

    return True


class PortalWrap:
    def __init__(self, hass: HomeAssistant, auth: Session, flat_list):
        self.hass = hass

        self.epd_dict = {
            item[CONF_PAYCODE]:
                Epd(
                    session=auth,
                    flat=item[CONF_FLAT],
                    paycode=item[CONF_PAYCODE]
            ) for item in flat_list
        }

        self.water_list = [
            Water(
                session=auth,
                flat=item[CONF_FLAT],
                paycode=item[CONF_PAYCODE]
            ) for item in flat_list
        ]

    @property
    def meters_list(self):
        meter_list = []
        for item in self.water_list:
            meter_list.extend(item.get_meter_list())
        return meter_list

    def get_meters_data_list(self):
        try:
            _LOGGER.debug("получение списка счетчиков с портала")
            result = {item.meter_id: item for item in self.meters_list}
            _LOGGER.debug(f"успешно получены следующие данные {result}")
            return result
        except BaseException as e:
            _LOGGER.error(f'данные не могут быть загружены {e}')

    async def fetch_data(self):
        async with async_timeout.timeout(20) as at:
            data = await self.hass.async_add_executor_job(
                self.get_meters_data_list
            )
        if at.expired:
            _LOGGER.error('таймаут получения данных с портала')
        return data

    def publish_water_usage(self, meter_list_to_update):
        _LOGGER.debug(
            f'входные данные для передачи на портал: {meter_list_to_update}')

        meter_list_to_update = {
            str(key): item for key, item in meter_list_to_update.items()}

        for item in self.meters_list:
            msg = {'meter_id': item.meter_id}
            try:
                if item.meter_id not in meter_list_to_update:
                    _LOGGER.warning(
                        f'счетчик {item.meter_id} отсутствует в настройках hass')
                    continue
                meter = meter_list_to_update[item.meter_id]
                item.cur_val = round(float(meter['value']), 2)
                msg['friendly_name'] = item.friendly_name = meter['friendly_name']

                if item.upload_value():
                    msg['usage'] = round(
                        float(item.cur_val) - float(item.value), 2)
                    self.hass.bus.fire(
                        'upload_water_success',
                        msg
                    )
            except BaseException as e:
                if not isinstance(e, WaterException):
                    _LOGGER.error(f'ошибка отправки данных на портал {e}')

                msg['error'] = str(e)
                self.hass.bus.fire(
                    'upload_water_fail',
                    msg
                )

        self.hass.bus.fire(
            'upload_water_finish',
            {}
        )

    def get_epd_service(self, *args):
        _LOGGER.debug(f'входные данные на получение ЕПД: {args}')
        month = int(args[0])
        year = int(args[1])
        data = args[2] if isinstance(args[2], dict) else json.loads(args[2])
        payload = args[3]

        try:
            if (payload is None and len(self.epd_dict.values()) > 1):
                raise BaseException(
                    f'необходимо указать payload для получения ЕПД')

            epd = list(self.epd_dict.values())[0]\
                if payload is None and len(self.epd_dict.values()) == 1\
                else self.epd_dict.get(str(payload), None)

            if (epd is None):
                raise BaseException(
                    f'указанный payload ({payload}) отсутвует в списке епд')

            _LOGGER.debug(f'вызов сервиса получения epd {data}')
            rsp = epd.get(year=year, month=month)

            _LOGGER.debug(f'успешно получен: {rsp.amount}')
            
            resp = {
                    'year': year,
                    'month': month,
                    'amount': rsp.amount,
                    'epd_type': rsp.epd_type[1],
                    'penalty': rsp.penalty,
                    'msg': '%04d_%02d. Статус оплаты: %s. Сумма %s' % (year, month, rsp.status[1], rsp.amount),
                    'content': base64.b64encode(rsp.content).decode(),
                    'filename': f'EPD-{rsp.period}.pdf'
                }
            resp.update(data)
            # data.update(
            #     {
            #         'year': year,
            #         'month': month,
            #         'amount': rsp.amount,
            #         'epd_type': rsp.epd_type[1],
            #         'penalty': rsp.penalty,
            #         'msg': '%04d_%02d. Статус оплаты: %s. Сумма %s' % (year, month, rsp.status[1], rsp.amount),
            #         'content': base64.b64encode(rsp.content).decode(),
            #         'filename': f'EPD-{rsp.period}.pdf'
            #     }
            # )
            _LOGGER.debug(f'успешно получен: {rsp.amount}')
            self.hass.bus.fire(
                'get_epd_success',
                resp
            )
        except BaseException as e:
            resp = {'msg': str(e)}
            resp.update(data)
            if not isinstance(e, EpdNotExist):
                _LOGGER.exception(
                    f'ошибка получения данных с портала {e}'
                )
            else:
                _LOGGER.info(
                    f'ошибка получения данных с портала {e}'
                )

            self.hass.bus.fire(
                'get_epd_error',
                data
            )
