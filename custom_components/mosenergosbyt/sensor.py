"""
Sensor for Mosenergosbyt cabinet.
Retrieves values regarding current state of accounts.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Dict, Optional, Tuple, Union, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.const import CONF_USERNAME, CONF_SCAN_INTERVAL, ATTR_ENTITY_ID, STATE_OK, \
    STATE_LOCKED, STATE_UNKNOWN, ATTR_ATTRIBUTION
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType, ConfigType, ServiceCallType

from . import DATA_CONFIG, CONF_ACCOUNTS, DEFAULT_SCAN_INTERVAL, DATA_API_OBJECTS, DATA_ENTITIES, DATA_UPDATERS, \
    CONF_LOGIN_TIMEOUT, DEFAULT_LOGIN_TIMEOUT, DEFAULT_METER_NAME_FORMAT, CONF_METER_NAME, CONF_ACCOUNT_NAME, \
    DEFAULT_ACCOUNT_NAME_FORMAT, DOMAIN, CONF_INVOICES, DEFAULT_INVOICE_NAME_FORMAT, CONF_INVOICE_NAME
from .mosenergosbyt import MosenergosbytException, ServiceType, MESElectricityMeter, _BaseMeter, \
    _BaseAccount, Invoice, IndicationsCountException, _SubmittableMeter

if TYPE_CHECKING:
    from types import MappingProxyType
    from .mosenergosbyt import API
    from homeassistant.core import Context

_LOGGER = logging.getLogger(__name__)

ENTITIES_ACCOUNT = 'account'
ENTITIES_METER_TARIFF = 'meter_tariff'

ATTR_METER_CODE = "meter_code"
ATTR_INDICATIONS = "indications"
ATTR_INCREMENTAL = "incremental"
ATTR_IGNORE_PERIOD = "ignore_period"
ATTR_NOTIFICATION = "notification"
ATTR_PERIOD = "period"
ATTR_CHARGED = "charged"
ATTR_INDICATIONS_DICT = "indications_dict"
ATTR_COMMENT = "comment"
ATTR_SUCCESS = "success"
ATTR_CALL_PARAMS = "call_params"

DEFAULT_MAX_INDICATIONS = 3
INDICATIONS_SCHEMA = vol.Any(
    {vol.All(int, vol.Range(1, DEFAULT_MAX_INDICATIONS)): cv.positive_int},
    vol.All([cv.positive_int], vol.Length(1, DEFAULT_MAX_INDICATIONS))
)

METER_IDENTIFIERS = {
    vol.Exclusive(ATTR_ENTITY_ID, 'meter_id'): cv.entity_id,
    vol.Exclusive(ATTR_METER_CODE, 'meter_id'): cv.string,
}
SCHEMA_METER_IDENTIFIERS = vol.Schema(METER_IDENTIFIERS, required=True, extra=vol.ALLOW_EXTRA)

CALCULATE_PUSH_INDICATIONS_SCHEMA = vol.All(
    SCHEMA_METER_IDENTIFIERS, {
        **METER_IDENTIFIERS,
        vol.Required(ATTR_INDICATIONS): INDICATIONS_SCHEMA,
        vol.Optional(ATTR_IGNORE_PERIOD, default=False): cv.boolean,
        vol.Optional(ATTR_INCREMENTAL, default=False): cv.boolean,
        vol.Optional(ATTR_NOTIFICATION, default=False): vol.Any(
            cv.boolean,
            persistent_notification.SCHEMA_SERVICE_CREATE,
        )
    }
)

SERVICE_PUSH_INDICATIONS = 'push_indications'
SERVICE_PUSH_INDICATIONS_PAYLOAD_SCHEMA = CALCULATE_PUSH_INDICATIONS_SCHEMA

SERVICE_CALCULATE_INDICATIONS = 'calculate_indications'
SERVICE_CALCULATE_INDICATIONS_PAYLOAD_SCHEMA = CALCULATE_PUSH_INDICATIONS_SCHEMA

EVENT_CALCULATION_RESULT = DOMAIN + "_calculation_result"
EVENT_PUSH_RESULT = DOMAIN + "_push_result"


async def _entity_updater(hass: HomeAssistantType, entry_id: str, user_cfg: ConfigType, async_add_entities,
                          now: Optional[datetime] = None) -> Union[bool, Tuple[int, int, int]]:
    _LOGGER.debug('Running updater for entry %s at %s' % (entry_id, now or datetime.now()))
    api: 'API' = hass.data.get(DATA_API_OBJECTS, {}).get(entry_id)
    if not api:
        _LOGGER.debug('Updater for entry %s found no API object' % entry_id)
        return False

    try:
        if not api.is_logged_in:
            await api.login()

        elif api.logged_in_at + user_cfg[CONF_LOGIN_TIMEOUT] <= datetime.utcnow():
            _LOGGER.debug('Refreshing authentication for %s' % entry_id)
            await api.logout()
            await api.login()

    except MosenergosbytException as e:
        _LOGGER.error('Authentication error: %s' % e)
        return False

    username = user_cfg[CONF_USERNAME]
    use_meter_filter = CONF_ACCOUNTS in user_cfg and user_cfg[CONF_ACCOUNTS]
    use_invoice_filter = CONF_INVOICES in user_cfg and user_cfg[CONF_INVOICES]

    # Fetch custom name formats (or select defaults)
    meter_name_format = user_cfg.get(CONF_METER_NAME, DEFAULT_METER_NAME_FORMAT)
    account_name_format = user_cfg.get(CONF_ACCOUNT_NAME, DEFAULT_ACCOUNT_NAME_FORMAT)
    invoice_name_format = user_cfg.get(CONF_INVOICE_NAME, DEFAULT_INVOICE_NAME_FORMAT)

    try:
        # Account fetching phase
        accounts = await api.get_accounts()
    except MosenergosbytException as e:
        _LOGGER.error('Error fetching accounts: %s' % e)
        return False

    created_entities = hass.data.setdefault(DATA_ENTITIES, {}).get(entry_id)
    if created_entities is None:
        created_entities = {}
        hass.data[DATA_ENTITIES][entry_id] = created_entities

    new_accounts = {}
    new_meters = {}
    new_invoices = {}

    tasks = []
    for account_code, account in accounts.items():
        _LOGGER.debug('Setting up account %s for username %s' % (account_code, username))

        account_entity = created_entities.get(account_code)
        if account_entity is None:
            account_entity = MESAccountSensor(account, account_name_format)
            new_accounts[account_code] = account_entity
            tasks.append(account_entity.async_update())
        else:
            account_entity.account = account
            account_entity.async_schedule_update_ha_state(force_refresh=True)

        try:
            # Process meters
            meters = await account.get_meters()

            if use_meter_filter:
                account_filter = user_cfg[CONF_ACCOUNTS][account_code]

                if account_filter is not True:
                    meters = {k: v for k, v in meters if k in account_filter}

            if account_entity.meter_entities is None:
                meter_entities = {}
                account_entity.meter_entities = meter_entities

            else:
                meter_entities = account_entity.meter_entities

                for meter_code in meter_entities.keys() - meters.keys():
                    tasks.append(hass.async_create_task(meter_entities[meter_code].async_remove()))
                    del meter_entities[meter_code]

            for meter_code, meter in meters.items():
                meter_entity = meter_entities.get(meter_code)

                if meter_entity is None:
                    meter_entity = MESMeterSensor(meter, meter_name_format)
                    meter_entities[meter_code] = meter_entity
                    new_meters[meter_code] = meter_entity
                    tasks.append(meter_entity.async_update())

                else:
                    meter_entity.meter = meter
                    meter_entity.async_schedule_update_ha_state(force_refresh=True)

        except MosenergosbytException as e:
            _LOGGER.error('Error retrieving meters: %s' % e)
            # we can still continue adding invoices

        # Check invoice filter
        if use_invoice_filter:
            invoice_filter = user_cfg[CONF_INVOICES]

            if invoice_filter is False:
                continue

            if invoice_filter is not True and account_code not in invoice_filter:
                continue

        try:
            # Process last invoice
            invoice = await account.get_last_invoice()

            if invoice:
                if account_entity.invoice_entity is None:
                    invoice_entity = MESInvoiceSensor(invoice, invoice_name_format)
                    account_entity.invoice_entity = invoice_entity
                    new_invoices[invoice.invoice_id] = invoice_entity
                    tasks.append(invoice_entity.async_update())

                else:
                    if account_entity.invoice_entity.invoice.invoice_id != invoice.invoice_id:
                        account_entity.invoice_entity.invoice = invoice
                        account_entity.async_schedule_update_ha_state(force_refresh=True)
        except MosenergosbytException as e:
            _LOGGER.error('Error fetching invoices: %s' % e)

    if tasks:
        await asyncio.wait(tasks)

    if new_accounts:
        async_add_entities(new_accounts.values())

    if new_meters:
        async_add_entities(new_meters.values())

    if new_invoices:
        async_add_entities(new_invoices.values())

    created_entities.update(new_accounts)

    _LOGGER.debug('Successful update on entry %s' % entry_id)
    _LOGGER.debug('New meters: %s' % new_meters)
    _LOGGER.debug('New accounts: %s' % new_accounts)
    _LOGGER.debug('New invoices: %s' % new_invoices)

    return len(new_accounts), len(new_meters), len(new_invoices)


async def async_register_services(hass: HomeAssistantType):
    if hass.services.has_service(DOMAIN, SERVICE_PUSH_INDICATIONS):
        return

    def _check_entity_id(entity_id: str, meter: 'MESMeterSensor'):
        return meter.meter and meter.entity_id == entity_id

    def _check_meter_code(meter_code: str, meter: 'MESMeterSensor'):
        return meter.meter and meter.meter.meter_code == meter_code

    def _find_meter_entity(call_data: 'MappingProxyType') -> Tuple[str, Optional['MESMeterSensor']]:
        entry_accounts: Dict[str, Dict[str, 'MESAccountSensor']] = hass.data.get(DATA_ENTITIES, {})

        if ATTR_ENTITY_ID in call_data:
            attr = ATTR_ENTITY_ID
            checker = partial(_check_entity_id, call_data[attr])
        else:
            attr = ATTR_METER_CODE
            checker = partial(_check_meter_code, call_data[attr])

        for entry_id, account_sensors in entry_accounts.items():
            for account_sensor in account_sensors.values():
                for meter in account_sensor.meter_entities.values():
                    if checker(meter):
                        return entry_id, meter

        return attr, None

    def _get_real_indications(meter_sensor: 'MESMeterSensor', call_data: 'MappingProxyType') \
            -> Union[Tuple[Union[int, float], ...]]:
        if call_data.get(ATTR_INCREMENTAL):
            return tuple([
                a + (s or l or 0)
                for a, l, s in zip(
                    call_data[ATTR_INDICATIONS],
                    meter_sensor.meter.last_indications,
                    meter_sensor.meter.submitted_indications,
                )
            ])
        return call_data[ATTR_INDICATIONS]

    def _fire_callback_event(event_id: str, event_data: Dict[str, Any], context: Optional['Context'] = None):
        _LOGGER.log(
            logging.INFO if event_data[ATTR_SUCCESS] else logging.ERROR,
            event_data[ATTR_COMMENT]
        )

        _LOGGER.debug("Firing event '%s' with data: %s" % (event_id, event_data))

        hass.bus.async_fire(
            event_type=event_id,
            event_data=event_data,
            context=context
        )

    async def async_push_indications(call: ServiceCallType):
        entry_id, meter_sensor = _find_meter_entity(call.data)

        event_data = {
            ATTR_CALL_PARAMS: dict(call.data),
            ATTR_SUCCESS: False,
            ATTR_ENTITY_ID: None,
            ATTR_METER_CODE: None,
            ATTR_INDICATIONS: None,
            ATTR_COMMENT: None,
        }

        if meter_sensor is None:
            event_data[ATTR_COMMENT] = 'Конфигурация `%s` не соответствует существующему счётчику' % entry_id

        else:
            meter_code = meter_sensor.meter.meter_code

            event_data[ATTR_ENTITY_ID] = meter_sensor.entity_id
            event_data[ATTR_METER_CODE] = meter_code

            if not isinstance(meter_sensor.meter, _SubmittableMeter):
                event_data[ATTR_COMMENT] = 'Счётчик \'%s\' не поддерживает передачу показаний' % meter_code

            else:
                ignore_period = call.data[ATTR_IGNORE_PERIOD]
                indications = _get_real_indications(meter_sensor, call.data)

                event_data[ATTR_INDICATIONS] = indications

                try:
                    comment = await meter_sensor.meter.submit_indications(
                        indications,
                        ignore_period_check=ignore_period,
                        ignore_indications_check=False
                    )

                    event_data[ATTR_COMMENT] = comment

                    event_data[ATTR_SUCCESS] = True

                    notification_content = call.data[ATTR_NOTIFICATION]
                    if notification_content:
                        payload = {
                            persistent_notification.ATTR_TITLE:
                                f"Переданы показания - №{meter_code}",
                            persistent_notification.ATTR_NOTIFICATION_ID:
                                f"mosenergosbyt_push_indications_{meter_code}",
                            persistent_notification.ATTR_MESSAGE:
                                f"Показания переданы для счётчика №{meter_code} за период "
                                f"{meter_sensor.meter.period_start_date} &mdash; {meter_sensor.meter.period_end_date}"
                        }

                        if notification_content is not True:
                            payload.update({
                                key: value.format(**event_data)
                                for key, value in notification_content.items()
                            })

                        hass.async_create_task(
                            hass.services.async_call(
                                persistent_notification.DOMAIN,
                                persistent_notification.SERVICE_CREATE,
                                payload,
                            )
                        )

                    # @TODO: this check might be ultra-redundant
                    if DATA_UPDATERS in hass.data and entry_id in hass.data[DATA_UPDATERS]:
                        _LOGGER.debug('Issuing account update')
                        hass.async_create_task(
                            hass.data[DATA_UPDATERS][entry_id][1]()
                        )

                except IndicationsCountException as e:
                    event_data[ATTR_COMMENT] = 'Error: %s' % e

                except MosenergosbytException as e:
                    event_data[ATTR_COMMENT] = 'API returned error: %s' % e

        _fire_callback_event(EVENT_PUSH_RESULT, event_data, call.context)

    async def async_calculate_indications(call: ServiceCallType):
        entry_id, meter_sensor = _find_meter_entity(call.data)

        event_data = {
            ATTR_CALL_PARAMS: dict(call.data),
            ATTR_SUCCESS: False,
            ATTR_ENTITY_ID: None,
            ATTR_METER_CODE: None,
            ATTR_INDICATIONS: None,
            ATTR_PERIOD: None,
            ATTR_CHARGED: None,
            ATTR_INDICATIONS_DICT: None,
            ATTR_COMMENT: None,
        }

        if meter_sensor is None:
            event_data[ATTR_COMMENT] = 'Конфигурация `%s` не соответствует существующему счётчику' % entry_id

        else:
            meter_code = meter_sensor.meter.meter_code

            if not isinstance(meter_sensor.meter, _SubmittableMeter):
                event_data[ATTR_COMMENT] = 'Счётчик \'%s\' не поддерживает подсчёт показаний' % meter_code

            else:

                ignore_period = call.data[ATTR_IGNORE_PERIOD]
                indications = _get_real_indications(meter_sensor, call.data)

                event_data[ATTR_INDICATIONS] = indications

                try:
                    calculation = await meter_sensor.meter.calculate_indications(
                        indications,
                        ignore_period_check=ignore_period,
                        ignore_indications_check=False
                    )

                    event_data[ATTR_PERIOD] = str(calculation.period)
                    event_data[ATTR_CHARGED] = calculation.charged
                    event_data[ATTR_INDICATIONS_DICT] = calculation.indications
                    event_data[ATTR_COMMENT] = calculation.comment

                    event_data[ATTR_SUCCESS] = True

                    notification_content = call.data[ATTR_NOTIFICATION]
                    if notification_content:
                        payload = {
                            persistent_notification.ATTR_TITLE:
                                f"Подсчёт начислений - №{meter_code}",
                            persistent_notification.ATTR_NOTIFICATION_ID:
                                f"mosenergosbyt_calculate_indications_{meter_code}",
                            persistent_notification.ATTR_MESSAGE: calculation.comment,
                        }

                        if notification_content is not True:
                            payload.update({
                                key: value.format(**event_data)
                                for key, value in notification_content.items()
                            })

                        hass.async_create_task(
                            hass.services.async_call(
                                persistent_notification.DOMAIN,
                                persistent_notification.SERVICE_CREATE,
                                payload,
                            )
                        )

                except IndicationsCountException as e:
                    event_data[ATTR_COMMENT] = 'Error: %s' % e

                except MosenergosbytException as e:
                    event_data[ATTR_COMMENT] = 'API returned error: %s' % e

        _fire_callback_event(EVENT_CALCULATION_RESULT, event_data, call.context)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PUSH_INDICATIONS,
        async_push_indications,
        SERVICE_PUSH_INDICATIONS_PAYLOAD_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALCULATE_INDICATIONS,
        async_calculate_indications,
        SERVICE_CALCULATE_INDICATIONS_PAYLOAD_SCHEMA
    )


async def async_setup_entry(hass: HomeAssistantType, config_entry: config_entries.ConfigEntry, async_add_devices):
    user_cfg = {**config_entry.data}
    username = user_cfg[CONF_USERNAME]

    _LOGGER.debug('Setting up entry for username "%s" from sensors' % username)

    if config_entry.source == config_entries.SOURCE_IMPORT:
        user_cfg = hass.data[DATA_CONFIG].get(username)
        scan_interval = user_cfg[CONF_SCAN_INTERVAL]

    elif CONF_SCAN_INTERVAL in user_cfg:
        scan_interval = timedelta(seconds=user_cfg[CONF_SCAN_INTERVAL])
        user_cfg[CONF_LOGIN_TIMEOUT] = timedelta(seconds=user_cfg[CONF_LOGIN_TIMEOUT])

    else:
        scan_interval = DEFAULT_SCAN_INTERVAL
        user_cfg[CONF_LOGIN_TIMEOUT] = DEFAULT_LOGIN_TIMEOUT

    update_call = partial(_entity_updater, hass, config_entry.entry_id, user_cfg, async_add_devices)

    try:
        result = await update_call()

        if result is False:
            return False

        if not sum(result):
            _LOGGER.warning('No accounts or meters discovered, check your configuration')
            return True

        await async_register_services(hass)

        hass.data.setdefault(DATA_UPDATERS, {})[config_entry.entry_id] = \
            (async_track_time_interval(hass, update_call, scan_interval), update_call)

        new_accounts, new_meters, new_invoices = result

        _LOGGER.info('Set up %d accounts, %d meters and %d invoices, will refresh every %s seconds'
                     % (new_accounts, new_meters, new_invoices, scan_interval.seconds + scan_interval.days*86400))
        return True

    except MosenergosbytException as e:
        raise PlatformNotReady('Error while setting up entry "%s": %s' % (config_entry.entry_id, str(e))) from None


# noinspection PyUnusedLocal
async def async_setup_platform(hass: HomeAssistantType, config: ConfigType, async_add_entities,
                               discovery_info=None):
    """Set up the sensor platform"""
    return False

ATTRIBUTION = "Data provided by Mosenergosbyt"


class MESEntity(Entity):
    def __init__(self):
        self._icon: Optional[str] = None
        self._state: Optional[Union[float, int, str]] = None
        self._unit: Optional[str] = None
        self._attributes: Optional[Dict[str, Union[float, int, str]]] = None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def state(self):
        """Return the state of the sensor"""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor"""
        return {**(self._attributes or {}), ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        return self._icon


class MESAccountSensor(MESEntity):
    """The class for this sensor"""
    def __init__(self, account: '_BaseAccount', name_format: str):
        super().__init__()

        self._name_format = name_format
        self._icon = 'mdi:flash-circle'
        self.account: '_BaseAccount' = account
        self.meter_entities: Optional[Dict[str, 'MESMeterSensor']] = None
        self.invoice_entity: Optional['Invoice'] = None

    async def async_update(self):
        """The update method"""
        remaining_days = None

        attributes = {
            'account_code': self.account.account_code,
            'address': self.account.address,
            'service_type': self.account.service_type.name.lower(),
        }

        if self.account.is_locked:
            attributes.update({
                'status': STATE_LOCKED,
                'reason': self.account.lock_reason
            })

            self._state = STATE_UNKNOWN
            self._unit = None

        else:
            try:
                _LOGGER.debug('Updating account %s' % self)
                last_payment = await self.account.get_last_payment()
                current_balance = await self.account.get_current_balance()

                if self.account.service_type == ServiceType.ELECTRICITY:
                    remaining_days = await self.account.get_remaining_days()

            except MosenergosbytException as e:
                message = 'Retrieving data from Mosenergosbyt failed: %s' % e
                if _LOGGER.level == logging.DEBUG:
                    _LOGGER.exception(message)
                else:
                    _LOGGER.error(message)
                return False

            attributes.update({
                'last_payment_date': last_payment['date'],
                'last_payment_amount': last_payment['amount'],
                'last_payment_status': last_payment['status'],
                'service_type': self.account.service_type.name.lower(),
                'status': STATE_OK,
            })

            if remaining_days is not None:
                attributes['remaining_days'] = remaining_days

            self._state = current_balance
            self._unit = 'руб.'

        self._attributes = attributes
        _LOGGER.debug('Update for account %s finished' % self)

    @property
    def name(self):
        """Return the name of the sensor"""
        return self._name_format.format(code=self.account.account_code,
                                        service_name=self.account.service_name,
                                        provider_name=self.account.provider_name)

    @property
    def unique_id(self):
        """Return the unique ID of the sensor"""
        return 'ls_' + str(self.account.service_id)


class MESMeterSensor(MESEntity):
    """The class for this sensor"""
    def __init__(self, meter: '_BaseMeter', name_format: str):
        super().__init__()

        self._icon = 'mdi:counter'
        self._name_format = name_format
        self.meter = meter

    async def async_update(self):
        """The update method"""
        attributes = {
            'meter_code': self.meter.meter_code,
            'account_code': self.meter.account_code,
            'remaining_days': self.meter.remaining_submit_days,
        }

        meter_status = self.meter.current_status

        if isinstance(self.meter, MESElectricityMeter):
            attributes['install_date'] = self.meter.install_date.isoformat()
            attributes['submit_period_start'] = self.meter.period_start_date.isoformat()
            attributes['submit_period_end'] = self.meter.period_end_date.isoformat()

            tariff_ids = self.meter.indications_ids

            tariff_costs = self.meter.tariff_costs
            for i, value in zip(tariff_ids, tariff_costs):
                attributes['cost_per_kwh_%s' % i] = value

            last_indications = self.meter.last_indications
            if last_indications:
                for i, value in zip(tariff_ids, self.meter.last_indications):
                    attributes['last_value_%s' % i] = value

            submitted_indications = self.meter.submitted_indications
            if submitted_indications:
                for i, value in zip(tariff_ids, self.meter.submitted_indications):
                    attributes['submitted_value_%s' % i] = value

            today_indications = self.meter.today_indications
            if today_indications:
                for i, value in zip(tariff_ids, self.meter.today_indications):
                    attributes['today_value_%s' % i] = value

        else:
            last_indications_dict = self.meter.last_indications_dict
            if last_indications_dict:
                for key, indication in last_indications_dict.items():
                    attributes['last_value_%s' % key] = indication[Invoice.ATTRS.VALUE]

                    for attribute in [Invoice.ATTRS.NAME, Invoice.ATTRS.COST, Invoice.ATTRS.UNIT]:
                        attributes['last_%s_%s' % (attribute, key)] = indication[attribute]

        self._state = STATE_OK if meter_status is None else meter_status
        self._attributes = attributes

    @property
    def name(self):
        """Return the name of the sensor"""
        return self._name_format.format(code=self.meter.meter_code)

    @property
    def unique_id(self):
        """Return the unique ID of the sensor"""
        return 'meter_' + str(self.meter.meter_code)


class MESInvoiceSensor(MESEntity):
    def __init__(self, invoice: 'Invoice', name_format: str):
        super().__init__()

        self._icon = 'mdi:receipt'
        self._unit = 'руб.'
        self._name_format = name_format
        self.invoice = invoice

    async def async_update(self):
        """The update method"""
        attributes = {
            'period': self.invoice.period.isoformat(),
            'invoice_id': self.invoice.invoice_id,
            'total': self.invoice.total,
            'paid': self.invoice.paid_amount,
            'initial': self.invoice.initial_balance,
            'charged': self.invoice.charged,
            'insurance': self.invoice.insurance,
            'benefits': self.invoice.benefits,
            'penalty': self.invoice.penalty,
            'service': self.invoice.service,
        }

        self._state = round(self.invoice.total, 2)
        self._attributes = attributes

    @property
    def name(self):
        """Return the name of the sensor"""
        return self._name_format.format(code=self.invoice.account.account_code)

    @property
    def unique_id(self):
        """Return the unique ID of the sensor"""
        return 'invoice_' + str(self.invoice.account.account_code)
