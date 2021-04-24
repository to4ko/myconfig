""" Basic Mosenergosbyt API interaction. """
import asyncio
import json
import logging
from _ast import arg
from abc import ABC
from datetime import datetime, date
from enum import IntEnum
from functools import partial
from hashlib import md5
from types import MappingProxyType
from typing import Optional, List, Dict, Union, Any, Type, TypeVar, Mapping, Tuple, Callable, NamedTuple, \
    Collection
from urllib import parse

import aiohttp
from dateutil.relativedelta import relativedelta
from dateutil.tz import tz

_LOGGER = logging.getLogger(__name__)

IndicationsType = Collection[Union[int, float]]
PaymentsList = List[Dict[str, Union[str, int, datetime]]]
InvoiceData = Dict[str, Any]
InvoiceList = List[InvoiceData]
IndicationsList = List[Dict[str, Any]]
AnyDate = Union[date, datetime]

MOSCOW_TIMEZONE = tz.gettz('Europe/Moscow')
OFFSET_START_TO_END = relativedelta(months=1, seconds=-1)


T = TypeVar('T')


DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    'AppleWebKit/537.36 (KHTML, like Gecko)'
    'Chrome/76.0.3809.100 Safari/537.36'
)


class DateUtil:
    @staticmethod
    def moscow_today(to_datetime: bool = False, timezone: Optional['tz'] = None) -> AnyDate:
        """
        Generate date object from Moscow time.
        :return:
        """
        now = datetime.now(tz=timezone or MOSCOW_TIMEZONE)
        return now if to_datetime else now.date()

    @staticmethod
    def month_start(to_datetime: bool = False, timezone: Optional['tz'] = None) -> AnyDate:
        today = DateUtil.moscow_today(True, timezone or MOSCOW_TIMEZONE)
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return month_start if to_datetime else month_start.date()

    @staticmethod
    def month_end(to_datetime: bool = False, timezone: Optional['tz'] = None) -> AnyDate:
        month_end = DateUtil.month_start(True, timezone or MOSCOW_TIMEZONE) + OFFSET_START_TO_END
        return month_end if to_datetime else month_end.date()

    @staticmethod
    def convert_date(value: Union[datetime, date], to: Type[Union[datetime, date]] = datetime,
                     _none_now: bool = True):
        return (to.today() if _none_now else None) if arg is None \
            else value if isinstance(arg, to) \
            else to.fromordinal(value.toordinal())

    @staticmethod
    def convert_date_arguments(*args: Union[datetime, date], _to: Type[Union[datetime, date]] = datetime,
                               _none_now=True, **kwargs: Union[datetime, date]):
        if args and kwargs:
            raise ValueError('Only one type of arguments (positional or keyword) can be provided')

        elif kwargs:
            return {kw: DateUtil.convert_date(v, _to, _none_now) for kw, v in kwargs.items()}

        return [DateUtil.convert_date(v, _to, _none_now) for v in args]


class _ListIntEnum(IntEnum):
    @classmethod
    def list(cls) -> List[int]:
        # noinspection PyTypeChecker
        return list(map(int, cls))


class ServiceType(_ListIntEnum):
    UNKNOWN_SERVICE_TYPE = -1
    ELECTRICITY = 1
    ELECTRICITY_TKO = 4

    @classmethod
    def _missing_(cls, value):
        return ServiceType.UNKNOWN_SERVICE_TYPE


class Provider(_ListIntEnum):
    MES = 1
    MOE = 2
    TMK_NRG = 3
    TMK_RTS = 4
    UFA = 5
    TKO = 6
    VLG = 7
    ORL = 8
    ORL_EPD = 9
    ALT = 10
    TMB = 11
    VLD = 12
    SAR = 13
    KSG = 14


PROVIDER_PROXY_LIST = {
    Provider.MES: "bytProxy",
    Provider.MOE: "smorodinaTransProxy",
    Provider.ORL: "orlBytProxy",
    Provider.TMK_NRG: "tomskProxy",
    Provider.TMK_RTS: "tomskProxy",
    Provider.UFA: "ufaProxy",
    Provider.TKO: "trashProxy",
    Provider.VLG: "vlgProxy",
    Provider.ALT: "altProxy",
    Provider.SAR: "sarProxy",
    Provider.TMB: "tmbProxy",
    Provider.VLD: "vldProxy",
    Provider.ORL_EPD: "orlProxy",
    Provider.KSG: "ksgProxy",
}


class ResponseCodes(_ListIntEnum):
    ERROR_NO_BUSINESS = 0
    SHOW_CAPTCHA = 114
    SHOW_CAPTCHA_PASSWORD_RESET = 127
    EMAIL_NOT_CONFIRMED = 128
    PHONE_NOT_CONFIRMED = 129
    PASSWORD_CHANGE_REQUIRED = 166
    EXTRA_CODE_REQUIRED = 192
    UNAUTHORIZATION = 201
    RESPONSE_RESULT = 1000
    SERVICE_NOT_FOUND = 6011
    BILLING_UNAVAILABLE = 6013


class API:
    """ Mosenergosbyt API class """
    BASE_URL = "https://my.mosenergosbyt.ru"
    AUTH_URL = BASE_URL + "/auth"
    REQUEST_URL = BASE_URL + "/gate_lkcomu"

    __global_requests_counter = 0

    def __init__(self, username: str, password: str, user_agent: Optional[str] = None, timeout: int = 5):
        self.__username = username
        self.__password = password

        self._user_agent: Optional[str] = user_agent

        if user_agent is not None:
            self._user_agent = user_agent.strip()

        self._session_id: Optional[str] = None
        self._id_profile = None
        self._token = None
        self._accounts = None
        self._logged_in_at = None

        self._pending_authentication_request: Optional[asyncio.Future] = None

        self._cookie_jar = aiohttp.CookieJar()
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def request(self, action, query, post_fields: Optional[Dict] = None, method='POST',
                      get_params: Optional[Dict] = None, fail_on_reauth: bool = False):
        if get_params is None:
            get_params = {}

        if self._user_agent is None:
            try:
                # noinspection PyUnresolvedReferences
                from fake_useragent import UserAgent
                loop = asyncio.get_event_loop()
                ua = await loop.run_in_executor(None, partial(UserAgent, fallback=DEFAULT_USER_AGENT))
                self._user_agent = ua['google chrome']

            except ImportError:
                self._user_agent = DEFAULT_USER_AGENT

        get_params['action'] = action
        get_params['query'] = query
        if self._session_id is not None:
            get_params['session'] = self._session_id

        encoded_params = parse.urlencode(get_params)
        request_url = self.REQUEST_URL + '?' + encoded_params
        response_text = None
        counter = API.__global_requests_counter + 1
        API.__global_requests_counter = counter

        try:
            async with aiohttp.ClientSession(cookie_jar=self._cookie_jar) as session:
                _LOGGER.debug('[%d] -> (%s) %s' % (counter, encoded_params, post_fields))
                async with session.post(request_url, data=post_fields) as response:
                    response_text = await response.text(encoding='utf-8')
                    _LOGGER.debug('[%d] <- (%d) %s' % (counter, response.status, response_text))
                    data = json.loads(response_text)

        except asyncio.exceptions.TimeoutError:
            raise MosenergosbytException('Timeout error (interaction exceeded %d seconds)'
                                         % self._timeout.total) from None

        except OSError as e:
            raise MosenergosbytException('Request error') from e

        except json.JSONDecodeError:
            _LOGGER.debug('Response contents: %s' % response_text)
            raise MosenergosbytException('Response contains invalid JSON') from None

        if data.get('success') is not None and data['success']:
            return data

        elif data.get('err_code', -1) == ResponseCodes.UNAUTHORIZATION:
            if fail_on_reauth:
                raise MosenergosbytException('Request returned')

            await self.login()
            return await self.request(
                action, query, post_fields,
                method, get_params,
                fail_on_reauth=True
            )

        raise MosenergosbytException('Request error [%d]: %s' % (data.get('err_code', -1),
                                                                 data.get('err_text', 'no description provided')))

    async def request_sql(self, query, post_fields: Optional[Dict] = None):
        return await self.request('sql', query, post_fields, 'POST')

    async def login(self):
        pending_request = self._pending_authentication_request
        if pending_request:
            if pending_request.done():
                self._pending_authentication_request = None
                return pending_request.result()

            await pending_request
            return pending_request.result()

        self._pending_authentication_request = asyncio.get_running_loop().create_future()

        try:
            self._session_id = None

            data = await self.request('auth', 'login', {
                'login': self.__username,
                'psw': self.__password,
                'remember': True,
                'vl_device_info': json.dumps({
                    'appver': '1.8.0',
                    'type': 'browser',
                    'userAgent': self._user_agent
                })
            })

            # @TODO: Multiple profiles possible?
            profile = data['data'][0]
            if profile['id_profile'] is None:
                raise MosenergosbytException(profile['nm_result'])

            self._id_profile = profile['id_profile']
            self._session_id = profile['session']
            self._token = profile['new_token']

            await self.request_sql('Init')
            await self.request_sql('NoticeRoutine')

            self._logged_in_at = datetime.utcnow()

        except Exception as e:
            self._pending_authentication_request.set_exception(e)
            raise self._pending_authentication_request.result()
        else:
            self._pending_authentication_request.set_result(True)
        finally:
            self._pending_authentication_request = None

        return True

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in_at

    @property
    def logged_in_at(self) -> datetime:
        return self._logged_in_at

    async def logout(self):
        self._id_profile = None
        self._token = None
        self._accounts = None
        self._logged_in_at = None

        self._cookie_jar.clear()

        return True

    async def get_accounts(self, return_unsupported_accounts: bool = False, suppress_unsupported_logging: bool = False)\
            -> Union[List['BaseAccount'], Tuple[List['BaseAccount'], List[Mapping[str, Any]]]]:
        response = await self.request_sql('LSList')

        tasks = []
        accounts_list: List[BaseAccount] = []
        unsupported_accounts: List[Mapping[str, Any]] = []

        for account_data in response['data']:
            try:
                account_obj = create_account_instance(account_data, self)

            except UnsupportedAccountException as e:
                if not suppress_unsupported_logging:
                    _LOGGER.warning('Unsupported account encountered: %s', e)

                if return_unsupported_accounts:
                    unsupported_accounts.append(account_data)

            else:
                accounts_list.append(account_obj)
                tasks.append(account_obj.update_info())

        if tasks:
            await asyncio.wait(tasks)

        if return_unsupported_accounts:
            return accounts_list, unsupported_accounts
        return accounts_list


class BaseAccount(ABC):
    """ Base account for implementing provider accounts. """
    ACCOUNT_URL = "https://my.mosenergosbyt.ru/accounts"

    def __init__(self, account_data: Dict[str, Any], api: API):
        self._account_data: Dict[str, Any] = account_data
        self._account_info: Optional[Dict[str, Any]] = None
        self._meter_objects: Optional[List[BaseMeter]] = None
        self.api: API = api

    async def update_info(self) -> Union[None, type(NotImplemented)]:
        """
        Update additional account information
        :return:
        """
        _LOGGER.debug('%s does not support info updates' % (self.__class__.__name__, ))
        return NotImplemented

    @property
    def data(self) -> Mapping[str, Any]:
        return MappingProxyType(self._account_data)

    @property
    def info(self) -> Optional[Mapping[str, Any]]:
        return MappingProxyType(self._account_info) if self._account_info else None

    # Properties
    @property
    def meter_objects(self) -> List['BaseMeter']:
        return self._meter_objects or []

    @property
    def meter_objects_dict(self) -> Dict[str, 'BaseMeter']:
        return dict(map(lambda x: (x.meter_code, x), self.meter_objects))

    @property
    def service_id(self):
        return self._account_data['id_service']

    @property
    def account_url(self):
        return self.ACCOUNT_URL + '/' + self._account_data['id_service']

    @property
    def account_code(self):
        return self._account_data['nn_ls']

    @property
    def address(self):
        return self._account_data['data']['nm_street']

    @property
    def provider_name(self) -> str:
        return self._account_data['nm_provider']

    @property
    def provider_type(self) -> Optional[Provider]:
        try:
            return Provider(int(self._account_data['kd_provider']))
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def service_type(self) -> ServiceType:
        try:
            return ServiceType(int(self._account_data['kd_service_type']))
        except (KeyError, ValueError, TypeError):
            return ServiceType.UNKNOWN_SERVICE_TYPE

    @property
    def service_name(self) -> str:
        return self._account_data['nm_type']

    @property
    def is_locked(self) -> bool:
        return self._account_data['kd_status'] > 1

    @property
    def lock_reason(self) -> Optional[str]:
        return self._account_data.get('nm_lock_msg')

    @property
    def description(self) -> Optional[str]:
        return self._account_data.get('nm_ls_description')

    # Base methods
    async def proxy_request(self, plugin: str, proxy_query: str, data: Optional[Dict] = None):
        data = {} if data is None else {**data}
        data['proxyquery'] = proxy_query

        return await self.direct_request(
            plugin,
            query=plugin,
            data=data
        )

    async def lk_byt_proxy(self, proxy_query, data: Optional[Dict] = None):
        return await self.proxy_request('bytProxy', proxy_query, data)

    async def direct_request(self, plugin: str, query: str, data: Optional[Dict] = None):
        data = {} if data is None else {**data}
        data['vl_provider'] = self._account_data['vl_provider']
        data['plugin'] = plugin

        return await self.api.request(
            action='sql',
            query=query,
            post_fields=data
        )

    # Shortcut methods
    async def get_contact_phone(self):
        contact_phone_key = 'nn_contact_phone'
        contact_phone = self._account_data.get(contact_phone_key)

        if 'nn_contact_phone' not in self._account_data:
            result = await self.api.request_sql('GetContactPhone', {'kd_provider': self._account_data['kd_provider']})
            contact_phone = result['data'][0][contact_phone_key]
            self._account_data[contact_phone_key] = contact_phone

        return contact_phone

    async def get_indications(self, start: AnyDate, end: Optional[AnyDate] = None) -> IndicationsList:
        start, end = DateUtil.convert_date_arguments(start, end, _to=datetime, _none_now=True)
        return await self._get_indications(start, end)

    async def get_indications_is_float(self) -> Optional[bool]:
        if '_pr_float' in self._account_data:
            return self._account_data['_pr_float']

        result = await self.api.request_sql('IndicationIsFloat', {'id_service': self._account_data['id_service']})
        pr_float = result.get('data', [{}])[0].get('pr_float')

        if pr_float is not None:
            self._account_data['_pr_float'] = pr_float

        return pr_float

    async def get_last_indications(self) -> Optional[Dict]:
        now = DateUtil.moscow_today(True)
        indications = await self._get_indications(now - relativedelta(months=1), now)
        return indications[0] if indications else None

    async def get_invoices(self, start: AnyDate, end: Optional[AnyDate] = None) -> List['Invoice']:
        start, end = DateUtil.convert_date_arguments(start, end, _to=datetime, _none_now=True)
        return await self._get_invoices(start, end)

    async def get_last_invoice(self) -> Optional['Invoice']:
        now = DateUtil.month_end(True)
        previous_month_start = DateUtil.month_start(True) - relativedelta(months=1)
        invoices = await self._get_invoices(previous_month_start, now)
        return invoices[0] if invoices else None

    async def get_last_payment(self) -> Optional[Dict]:
        payments = await self.get_latest_payments()
        if not payments:
            return None
        return payments[0]

    async def get_latest_payments(self, months: int = 3) -> PaymentsList:
        now = DateUtil.moscow_today(True)
        return await self.get_payments(now - relativedelta(months=months), now)

    async def get_payments(self, start: AnyDate, end: Optional[AnyDate] = None) -> PaymentsList:
        start, end = DateUtil.convert_date_arguments(start, end, _to=datetime)
        return await self._get_payments(start, end)

    # Common methods
    async def _common_proxy_indications(
            self,
            start: datetime,
            end: datetime,
            plugin: str,
            proxy_query: str = 'Indications'
    ) -> List[Dict]:
        response = await self.proxy_request(
            plugin=plugin,
            proxy_query=proxy_query,
            data={
                'dt_st': start.isoformat(),
                'dt_en': end.isoformat()
            }
        )

        return [
            {
                'date': datetime.fromisoformat(indication['dt_indication']),
                '_taken_by': indication['nm_take'],
                '_source': indication['nm_indication_take'],
                'meters': {
                    k[-2:]: v
                    for k, v in indication.items()
                    if k[:-1] == 'vl_t'
                }
            }
            for indication in response['data']
        ]

    async def _common_proxy_invoices(
            self,
            start: datetime,
            end: datetime,
            plugin: str,
            proxy_query: str = 'Invoice'
    ) -> List['Invoice']:
        response = await self.proxy_request(
            plugin=plugin,
            proxy_query=proxy_query,
            data={
                'dt_st': start.isoformat(),
                'dt_en': end.isoformat(),
            }
        )

        invoices = []
        for invoice in response['data']:
            charges = {}
            for i, charge in enumerate(invoice['data_detail'], start=1):
                charge_part_iter = iter(charge)

                charge_dict = {}

                try:
                    head_part = next(charge_part_iter)
                    charge_dict['name'] = head_part['nm_value']
                    charge_dict['total'] = head_part['vl_value']

                    value_part = next(charge_part_iter)
                    charge_dict['unit'] = value_part['nm_mu']
                    charge_dict['value'] = value_part['vl_value']

                    tariff_part = next(charge_part_iter)
                    charge_dict['cost'] = tariff_part['vl_value']

                except StopIteration:
                    raise MosenergosbytException('Invoice (%s) data incomplete', invoice['id_korr']) from invoice

                charges['t%d' % i] = charge_dict

            calculations = {}
            for section in invoice['data_common']:
                section_name = section['nm_value']
                value = section['vl_value']
                if section_name.startswith('Итого'):
                    calculations[Invoice.TOTAL] = value
                elif 'начислено' in section_name:
                    calculations[Invoice.COSTS.CHARGED] = value
                elif 'долж' in section_name:
                    calculations[Invoice.INITIAL_BALANCE] = value
                elif 'поступ' in section_name:
                    calculations[Invoice.DEDUCTIONS.PAYMENTS] = value

            invoices.append(
                Invoice(
                    account=self,
                    invoice_id=str(invoice['id_korr']),
                    period=datetime.fromisoformat(invoice['dt_period']).date(),
                    calculations=calculations,
                    charges=charges
                )
            )

        return invoices

    @classmethod
    def _common_generate_indications_from_charges(cls, charges: List[Dict[str, Any]], with_calculations: bool = False) \
            -> Dict[str, Dict[str, Union[float, Dict[str, float]]]]:
        indications = {}
        for charge in charges:
            charge_dict = {
                Invoice.ATTRS.NAME: charge['nm_service'],
                Invoice.ATTRS.UNIT: charge['nm_measure_unit'],
                Invoice.ATTRS.VALUE: charge['vl_charged_volume'],
                Invoice.ATTRS.COST: charge['vl_tariff'],
            }

            if with_calculations:
                charge_dict[Invoice.ATTRS.CALCULATIONS] = {
                    Invoice.ADJUSTMENTS: charge['sm_recalculations'],
                    Invoice.INITIAL_BALANCE: charge['sm_start'],
                    Invoice.COSTS.CHARGED: charge['sm_charged'],
                    Invoice.COSTS.PENALTY: charge['sm_penalty'],
                    Invoice.DEDUCTIONS.BENEFITS: charge['sm_benefits'],
                    Invoice.DEDUCTIONS.PAYMENTS: charge['sm_payed'],
                    Invoice.TOTAL: charge['sm_total'],
                }

            indications[cls._common_generate_indication_id(charge['nm_service'])] = charge_dict

        return indications

    @staticmethod
    def _common_generate_indication_id(name: str):
        lower_name = name.lower()
        if 'тко' in lower_name:
            return 'tko'
        elif 'ночь' in lower_name:
            return 'night'
        elif 'день' in lower_name:
            return 'day'
        return md5(lower_name.encode('utf-8')).hexdigest()[:6]

    async def _common_proxy_charge_details(
            self,
            start: datetime,
            end: datetime,
            plugin: str,
            proxy_query: str = 'AbonentChargeDetail'
    ) -> List['Invoice']:
        response = await self.proxy_request(
            plugin=plugin,
            proxy_query=proxy_query,
            data={
                'dt_period_start': start.isoformat(),
                'dt_period_end': end.isoformat(),
                'kd_tp_mode': 1
            }
        )

        return [
            Invoice(
                account=self,
                invoice_id=invoice['vl_report_uuid'],
                period=datetime.fromisoformat(invoice_group['dt_period']).date(),
                calculations={
                    Invoice.INITIAL_BALANCE: invoice['sm_start'],
                    Invoice.ADJUSTMENTS: invoice['sm_recalculations'],
                    Invoice.COSTS.CHARGED: invoice['sm_charged'],
                    Invoice.COSTS.INSURANCE: invoice['sm_insurance'],
                    Invoice.COSTS.PENALTY: invoice['sm_penalty'],
                    Invoice.COSTS.SERVICE: invoice['sm_tovkgo'],
                    Invoice.DEDUCTIONS.BENEFITS: invoice['sm_benefits'],
                    Invoice.DEDUCTIONS.PAYMENTS: invoice['sm_payed'],
                    Invoice.TOTAL: invoice['sm_total'],
                },
                charges=self._common_generate_indications_from_charges(invoice['child'], with_calculations=True)
            )
            for invoice_group in response['data']
            for invoice in invoice_group.get('child', [])
        ]

    async def _common_proxy_remaining_days(
            self,
            plugin: str,
            proxy_query: str = 'IndicationCounter'
    ) -> Optional[Tuple[bool, int]]:
        response = await self.proxy_request(plugin=plugin, proxy_query=proxy_query)
        data = response.get('data', [])
        if data:
            data_first = data[0]
            if isinstance(data_first, Mapping):
                return bool(data_first.get('pr_ind_avail')), max(0, int(data_first.get('nn_days', 0)))

        return None

    async def _common_proxy_payments(
            self,
            start: datetime,
            end: datetime,
            plugin: str,
            proxy_query: str = 'Pays',
            key_date: str = 'dt_pay',
            key_amount: str = 'sm_pay',
            key_status: str = 'nm_status',
    ) -> List[Dict[str, Any]]:
        response = await self.proxy_request(
            plugin=plugin,
            proxy_query=proxy_query,
            data={
                'dt_st': start.isoformat(),
                'dt_en': end.isoformat()
            }
        )

        return [
            {
                'date': datetime.fromisoformat(payment[key_date]),
                'amount': payment[key_amount],
                'status': payment[key_status],
            }
            for payment in response['data']
            if payment
        ]

    async def _common_proxy_balance(
            self,
            plugin: str,
            proxy_query: str = 'CurrentBalance',
            key_balance: str = 'vl_balance',
    ):
        response = await self.proxy_request(plugin, proxy_query)
        return response['data'][0][key_balance]

    # Methods to override
    async def get_current_balance(self) -> float:
        raise NotImplementedError

    async def _get_indications(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def _get_invoices(self, start: datetime, end: datetime) -> List['Invoice']:
        raise NotImplementedError

    async def get_meters(self) -> List['BaseMeter']:
        raise NotImplementedError

    async def _get_payments(self, start: datetime, end: datetime) -> PaymentsList:
        raise NotImplementedError

    async def get_submission_availability(self) -> Optional[Tuple[bool, int]]:
        raise NotImplementedError


# Dictionary that holds all registered supported account types
SUPPORTED_PROVIDERS: Dict[Tuple[Provider, Optional[ServiceType]], Type['BaseAccount']] = {}


def get_account_class(
        provider_id: Union[Provider, int],
        service_type: Optional[Union[ServiceType, int]] = None,
        generic_fallback: bool = False
) -> Optional[Type['BaseAccount']]:
    """
    Lookup account class based on provider and service type parameters.
    """
    if not isinstance(provider_id, Provider):
        provider_id = Provider(provider_id)

    if service_type is None:
        return SUPPORTED_PROVIDERS.get((provider_id, None))
    
    if not isinstance(service_type, ServiceType):
        try:
            service_type = ServiceType(service_type)
        except (KeyError, ValueError, TypeError):
            raise ValueError('Invalid service type provided: %s' % (service_type,))
    
    account_cls = SUPPORTED_PROVIDERS.get((provider_id, service_type))

    if generic_fallback and account_cls is None:
        return get_account_class(provider_id=provider_id, service_type=None, generic_fallback=False)

    return account_cls


def register_account_class(
        account_cls: Type['BaseAccount'],
        provider_id: Union[Provider, int],
        service_type: Optional[Union[ServiceType, int]] = None,
        override: bool = False
):
    """Register account class with the support dictionary"""
    if account_cls is BaseAccount:
        raise ValueError('Cannot register base account')

    if not isinstance(provider_id, Provider):
        provider_id = Provider(provider_id)

    if not (service_type is None or isinstance(service_type, ServiceType)):
        service_type = ServiceType(service_type)

    if not override:
        existing_account_cls = get_account_class(
            provider_id=provider_id,
            service_type=service_type,
            generic_fallback=False
        )

        if not (existing_account_cls is None or existing_account_cls is account_cls):
            error_msg = f'Provider "{provider_id.name}" (ID: {provider_id.value}) with '

            if service_type is None:
                error_msg += 'generic service type'
            else:
                error_msg += f'service type "{service_type.name}" (ID: {service_type.value})'

            error_msg += ' is already registered'
            
            raise ValueError(error_msg)
        
    SUPPORTED_PROVIDERS[(provider_id, service_type)] = account_cls


def decorate_register_account_class(
        provider_id: Union[Provider, int],
        service_type: Optional[Union[ServiceType, int]] = None,
        override: bool = False
) -> Callable[[Type['BaseAccount']], Type['BaseAccount']]:
    """Decorator for `register_account_class` for use with BaseAccount (base account class) subclasses"""
    def _internal(account_cls: Type['BaseAccount']) -> Type['BaseAccount']:
        register_account_class(
            account_cls=account_cls,
            provider_id=provider_id,
            service_type=service_type,
            override=override
        )
        return account_cls

    _internal.__doc__ = f"Decorator to register account class as supporting {provider_id} / {service_type}"

    return _internal


def create_account_instance(account_data: Dict[str, Any], api: API, generic_fallback: bool = True) -> 'BaseAccount':
    provider_id = Provider(int(account_data['kd_provider']))

    try:
        service_type = ServiceType(int(account_data['kd_service_type'])) if 'kd_service_type' in account_data else None
    except (KeyError, ValueError, TypeError):
        service_type = None

    account_cls = get_account_class(
        provider_id=provider_id,
        service_type=service_type,
        generic_fallback=generic_fallback
    )

    if account_cls is None:
        error_msg = f'Provider "{provider_id.name}" (ID: {provider_id.value}) with '

        if service_type is None:
            error_msg += 'generic service type'
        else:
            error_msg += f'service type "{service_type.name}" (ID: {service_type.value})'

        error_msg += ' is not supported'
        
        raise ValueError(error_msg)
    
    return account_cls(account_data, api)


@decorate_register_account_class(Provider.MES)
class MESAccount(BaseAccount):
    """ Mosenergosbyt Account class """
    # Base implementation
    async def update_info(self) -> None:
        response = await self.lk_byt_proxy('LSInfo')
        self._account_info = response['data'][0]

    async def get_meters(self) -> List['MESElectricityMeter']:
        response = await self.lk_byt_proxy('Meters')

        if self._meter_objects is None:
            self._meter_objects = [
                MESElectricityMeter(
                    account=self,
                    data=meter_data
                )
                for meter_data in response['data']
                if meter_data
            ]
            return self._meter_objects

        keep_meter_objects = []

        existing_meter_objects = dict({
            meter.meter_code: i
            for i, meter in enumerate(self._meter_objects)
        })

        for meter_data in response['data']:
            if not meter_data:
                continue
            meter_code = meter_data['nm_meter_num']
            meter_index = existing_meter_objects.get(meter_code)

            if meter_index is None:
                meter = MESElectricityMeter(
                    account=self,
                    data=meter_data
                )

            else:
                meter = self._meter_objects[meter_index]
                meter.data = meter_data

            keep_meter_objects.append(meter)

        self._meter_objects = keep_meter_objects

        return keep_meter_objects

    async def _get_invoices(self, start: datetime, end: datetime) -> List['Invoice']:
        return await self._common_proxy_invoices(start, end, 'bytProxy')

    async def _get_payments(self, start: datetime, end: datetime) -> PaymentsList:
        return await self._common_proxy_payments(start, end, 'bytProxy')

    async def get_current_balance(self) -> float:
        return await self._common_proxy_balance('bytProxy')

    async def get_submission_availability(self) -> Optional[Tuple[bool, int]]:
        return await self._common_proxy_remaining_days('bytProxy')

    async def _get_indications(self, start: datetime, end: datetime) -> IndicationsList:
        return await self._common_proxy_indications(start, end, 'bytProxy')


@decorate_register_account_class(Provider.TKO)
class TKOAccount(BaseAccount):
    """ Mosenergosbyt + TKO account class """

    # Connection
    async def lk_trash_proxy(self, proxy_query: str, data: Optional[Dict] = None):
        return await self.proxy_request('trashProxy', proxy_query, data)

    # Base implementation
    async def _get_invoices(self, start: datetime, end: datetime) -> List['Invoice']:
        return await self._common_proxy_charge_details(start, end, 'trashProxy')

    async def _get_payments(self, start: datetime, end: datetime) -> PaymentsList:
        return await self._common_proxy_payments(start, end, 'trashProxy',
                                                 proxy_query='AbonentPays',
                                                 key_status='nm_pay_state')

    async def _get_indications(self, start: datetime, end: datetime) -> IndicationsList:
        response = await self.lk_trash_proxy('AbonentChargeDetail', {
            'dt_period_start': start.isoformat(),
            'dt_period_end': end.isoformat(),
            'kd_tp_mode': 1
        })

        return [
            self._common_generate_indications_from_charges(invoice['child'], with_calculations=False)
            for invoice_group in response.get('data', [])
            for invoice in invoice_group.get('child', [])
        ]

    async def get_meters(self) -> List['TKOIndicationMeter']:
        indications = await self.get_last_indications()

        if self._meter_objects is None:
            meter_objects = [TKOIndicationMeter(self, indications)]
            self._meter_objects = meter_objects
            return meter_objects

        self._meter_objects[0].data = indications
        return self._meter_objects

    async def get_current_balance(self) -> float:
        response = await self.lk_trash_proxy('AbonentCurrentBalance')
        return -(response['data'][0]['sm_balance'])

    async def get_submission_availability(self) -> Optional[Tuple[bool, int]]:
        # @TODO: approximate using bill data
        return None

    # Additional overrides
    async def get_last_indications(self) -> Optional[Dict]:
        now = DateUtil.moscow_today(True)
        previous_month_start = DateUtil.month_start(True) - relativedelta(months=1)
        indications = await self._get_indications(previous_month_start, now)
        return indications[0] if indications else None


@decorate_register_account_class(Provider.MOE)
class MOEAccount(MESAccount):
    async def lk_smorodina_trans_proxy(self, proxy_query, data: Optional[Dict] = None):
        return await self.proxy_request('smorodinaTransProxy', proxy_query, data)

    async def get_current_balance(self) -> float:
        response = await self.lk_smorodina_trans_proxy('AbonentCurrentBalance')
        return -(response['data'][0]['sm_balance'])

    async def get_meters(self) -> List['MOEGenericMeter']:
        response = await self.lk_smorodina_trans_proxy('AbonentEquipment')

        if self._meter_objects is None:
            self._meter_objects = [
                MOEGenericMeter(
                    account=self,
                    data=meter_data
                )
                for meter_data in response['data']
                if meter_data
            ]
            return self._meter_objects

        keep_meter_objects = []

        existing_meter_objects = dict({
            meter.meter_code: i
            for i, meter in enumerate(self._meter_objects)
        })

        for meter_data in response['data']:
            if not meter_data:
                continue
            meter_code = meter_data['nm_counter']
            meter_index = existing_meter_objects.get(meter_code)

            if meter_index is None:
                meter = MOEGenericMeter(
                    account=self,
                    data=meter_data
                )

            else:
                meter = self._meter_objects[meter_index]
                meter.data = meter_data

            keep_meter_objects.append(meter)

        self._meter_objects = keep_meter_objects

        return keep_meter_objects

    async def _get_invoices(self, start: datetime, end: datetime) -> List['Invoice']:
        return await self._common_proxy_charge_details(start, end, 'smorodinaTransProxy')

    async def _get_payments(self, start: datetime, end: datetime) -> PaymentsList:
        return await self._common_proxy_payments(start, end, 'smorodinaTransProxy',
                                                 proxy_query='AbonentPays',
                                                 key_status='nm_pay_state')

    update_info = BaseAccount.update_info


@decorate_register_account_class(Provider.KSG)
class KSGAccount(BaseAccount):
    # Connection
    async def lk_ksg_proxy(self, proxy_query, data: Optional[Dict] = None):
        return await self.proxy_request('ksgProxy', proxy_query, data)

    # Base implementation
    async def update_info(self) -> None:
        response = await self.lk_ksg_proxy('LSInfo')
        self._account_info = response['data'][0]

    async def get_meters(self) -> List['KSGElectricityMeter']:
        # @TODO: partially redundant calls
        await self.update_info()
        indications = await self.get_last_indications()

        keep_meter_objects = []

        if self._meter_objects:
            meter_code = self._account_info['nn_meter'].strip()
            keep_meter_objects = []
            for meter_object in self._meter_objects:
                if meter_object.meter_code == meter_code:
                    keep_meter_objects.append(meter_object)

        if keep_meter_objects:
            for meter_object in keep_meter_objects:
                meter_object.data = indications
        else:
            new_meter = KSGElectricityMeter(
                account=self,
                data=indications,
            )
            keep_meter_objects.append(new_meter)

        self._meter_objects = keep_meter_objects

        return self._meter_objects

    async def _get_invoices(self, start: datetime, end: datetime) -> List['Invoice']:
        return await self._common_proxy_invoices(start, end, 'ksgProxy')

    async def _get_payments(self, start: datetime, end: datetime) -> PaymentsList:
        return await self._common_proxy_payments(start, end, 'ksgProxy')

    async def get_current_balance(self) -> float:
        response = await self.lk_ksg_proxy('CurrentBalance')
        return response['data'][0]['vl_balance']

    async def get_submission_availability(self) -> Optional[Tuple[bool, int]]:
        return await self._common_proxy_remaining_days('ksgProxy')

    async def _get_indications(self, start: datetime, end: datetime) -> IndicationsList:
        return await self._common_proxy_indications(start, end, 'ksgProxy')


class Tariff(NamedTuple):
    id: str
    name: Optional[str]
    unit: Optional[str]
    description: Optional[str]
    cost: Optional[float]


class BaseMeter(ABC):
    DataType = TypeVar('DataType')

    def __init__(self, account: 'BaseAccount', data: DataType):
        """
        Initializes Meter object
        :param account: Tied account
        :param data: Meter data
        """
        self._account = account

        self.data = data

    def __str__(self):
        return '%s[%s]' % (type(self).__name__, self.meter_code)

    def __repr__(self):
        return '<%s>' % self

    @property
    def account(self) -> BaseAccount:
        return self._account

    @property
    def data(self) -> DataType:
        return self._data

    @data.setter
    def data(self, value: DataType):
        self._data = value

    @property
    def account_code(self) -> str:
        """
        Parent account code accessor.
        :return:
        """
        return self._account.account_code

    # Override in inherent classes
    @property
    def meter_code(self) -> str:
        raise NotImplementedError

    @property
    def model(self) -> Optional[str]:
        """
        Meter model shortcut accessor.
        :return: Meter model string
        """
        return None

    @property
    def install_date(self) -> Optional[date]:
        return None

    @property
    def tariffs(self) -> List[Tariff]:
        info = self._account.info

        return [
            Tariff(
                id=tariff_id,
                name=info.get('nm_' + tariff_id),
                description=info.get('nm_' + tariff_id + '_description'),
                cost=info.get('vl_' + tariff_id + '_tariff'),
                unit='кВт*ч'
            )
            for tariff_id in self.tariff_ids
        ]

    @property
    def tariff_ids(self) -> List[str]:
        tariff_ids = set()

        for key, value in self._account.info.items():
            if value is not None:
                parts = key.split('_')
                if len(parts) > 1 and parts[1][0] == 't' and parts[1][1:].isnumeric():
                    tariff_ids.add(parts[1])

        return sorted(tariff_ids)

    @property
    def tariff_count(self) -> int:
        return len(self.tariff_ids)

    @property
    def today_indications(self) -> List[Optional[float]]:
        raise NotImplementedError

    @property
    def last_indications(self) -> List[Optional[float]]:
        raise NotImplementedError

    @property
    def _empty_indications_list(self) -> List[type(None)]:
        return [None] * self.tariff_count

    @property
    def submitted_indications(self) -> List[Optional[float]]:
        """
        Submitted indications accessor.
        Skims meter data for submitted indications in current period, and prepares data.
        :return:
        """
        last_indications_date = self.last_indications_date
        if last_indications_date is not None:
            period_start_date = self.period_start_date
            if period_start_date is not None:
                period_end_date = self.period_end_date
                if period_end_date is not None:
                    if period_start_date <= last_indications_date <= period_end_date:
                        return self.last_indications

        # Out-of-period today submission
        today_indications = self.today_indications

        if any(today_indications):
            return today_indications

        return self._empty_indications_list

    @property
    def invoice_indications(self) -> List[Optional[float]]:
        return self.last_indications

    @property
    def last_indications_date(self) -> Optional[date]:
        return None

    @property
    def period_start_date(self) -> Optional[date]:
        return None

    @property
    def period_end_date(self) -> Optional[date]:
        return None

    @property
    def current_status(self) -> Optional[str]:
        return None


class SubmittableMeter(BaseMeter, ABC):
    async def _check_submit_period(self) -> None:
        period_start_date = self.period_start_date
        period_end_date = self.period_end_date

        if period_start_date is None or period_end_date is None:
            submission_availability = await self._account.get_submission_availability()
            if submission_availability is None:
                _LOGGER.warning('Could not determine period start/end date(s), assuming failed period check')
                raise SubmissionPeriodException('Could not identify submission period')

            active, remaining_days = submission_availability

            if not active:
                raise SubmissionPeriodException('Submission is not active')

        else:
            period = DateUtil.moscow_today()

            if period < period_start_date or period > period_end_date:
                raise SubmissionPeriodException('Submission period not within range')

    async def _common_prepare_indications_request(self, indications: IndicationsType, check_if_float: bool = True):
        if check_if_float:
            _converter = float if await self._account.get_indications_is_float() else int
        else:
            def _converter(x: Any):
                if isinstance(x, (int, float)):
                    return x
                return int(x)

        request_dict = {
            'vl_%s' % tariff_id: _converter(indication)
            for tariff_id, indication in zip(self.tariff_ids, indications)
            if indication is not None
        }

        request_dict['pr_flat_meter'] = self._data.get('pr_flat_meter', 0)

        request_dict['nn_phone'] = await self._account.get_contact_phone()

        return request_dict

    async def _common_submit_indications(
            self,
            indications: IndicationsType,
            plugin: str,
            proxy_query: str = 'SaveIndications',
            check_if_float: bool = True
    ) -> str:
        request_dict = await self._common_prepare_indications_request(indications, check_if_float=check_if_float)
        result = await self._account.proxy_request(plugin, proxy_query, request_dict)

        result_data = result.get('data')
        if result_data:
            data = result_data[0]
            if data['kd_result'] == ResponseCodes.RESPONSE_RESULT:
                return data['nm_result']

            if data['kd_result'] == 2:
                raise IndicationsCountException('Sent invalid indications count')

        _LOGGER.debug('Indications saving response data: %s', result)
        raise MosenergosbytException('Unknown error')

    async def _common_calculate_indications(
            self,
            indications: IndicationsType,
            plugin: str,
            proxy_query: str = 'CalcCharge',
            check_if_float: bool = True,
    ) -> 'ChargeCalculation':
        request_dict = await self._common_prepare_indications_request(indications, check_if_float=check_if_float)
        result = await self._account.proxy_request(plugin, proxy_query, request_dict)

        result_data = result.get('data')
        if result_data:
            data = result_data[0]
            if data['kd_result'] == ResponseCodes.RESPONSE_RESULT:
                return ChargeCalculation(self, indications, data['sm_charge'], data['nm_result'], data['pr_correct'])

            if data['kd_result'] == 2:
                raise IndicationsCountException('Sent invalid indications count')

        _LOGGER.debug('Indications calculation response data: %s' % result)
        raise MosenergosbytException('Unknown error')

    async def _check_submit_values(self, indications: IndicationsType) -> None:
        tariff_count = self.tariff_count

        if len(indications) != tariff_count:
            raise IndicationsCountException(
                'Indications count (%d) is not equal to meter tariff count (%d)',
                len(indications), tariff_count
            )

        try:
            last_indications = self.last_indications

        except (MosenergosbytException, NotImplementedError):
            _LOGGER.debug('Could not determine last indications, assuming none provided')

        else:
            for last_indication, new_indication, tariff_id in zip(last_indications, indications, self.tariff_ids):
                if last_indication is None:
                    continue

                if last_indication > new_indication:
                    raise IndicationsThresholdException(
                        'Indication "%s" (%d) is less than last indication value (%d)' %
                        (tariff_id, new_indication, last_indication)
                    )
                elif int(last_indication) == int(new_indication):
                    raise IndicationsThresholdException(
                        'Indication "%s" (%d) is equal to last indication value integer-wise (%d)' %
                        (tariff_id, int(new_indication), int(last_indication))
                    )

    async def _submit_indications(self, indications: IndicationsType) -> str:
        raise NotImplementedError

    async def submit_indications(self, indications: IndicationsType, ignore_period_check: bool = False,
                                 ignore_indications_check: bool = False) -> str:
        """
        Submit indications to Mosenergosbyt.
        Use this method with caution! There are safeguards in place to prevent an out-of-period and incomplete
        submissions. Override these safeguards at your own risk.
        :param indications: Indications list / dictionary
        :param ignore_period_check: Ignore out-of-period safeguard
        :param ignore_indications_check: Ignore indications miscount or lower-than-threshold safeguard
        :return: Status comment
        """
        if not ignore_indications_check:
            await self._check_submit_values(indications)

        if not ignore_period_check:
            await self._check_submit_period()

        return await self._submit_indications(indications)

    async def _calculate_indications(self, indications: IndicationsType) -> 'ChargeCalculation':
        raise NotImplementedError

    async def calculate_indications(self, indications: IndicationsType, ignore_period_check: bool = False,
                                    ignore_indications_check: bool = False) -> 'ChargeCalculation':
        """
        Calculate indications charges with Mosenergosbyt.
        Use this method with caution! There are safeguards in place to prevent an out-of-period and incomplete
        submissions. Override these safeguards at your own risk.
        :param indications: Indications list / dictionary
        :param ignore_period_check: Ignore out-of-period safeguard
        :param ignore_indications_check: Ignore indications miscount or lower-than-threshold safeguard
        :return: Charge calculation object
        """
        if not ignore_indications_check:
            await self._check_submit_values(indications)

        if not ignore_period_check:
            await self._check_submit_period()

        return await self._calculate_indications(indications)


class MESElectricityMeter(SubmittableMeter):
    """ Mosenergosbyt meter class """

    @property
    def meter_code(self) -> str:
        return self._data['nm_meter_num']

    @property
    def install_date(self) -> Optional[date]:
        """
        Meter install date accessor.
        :return: Installation date object
        """
        install_date = self._data.get('dt_meter_install')
        if install_date:
            return datetime.fromisoformat(install_date).date()

    @property
    def model(self) -> Optional[str]:
        """
        Meter model shortcut accessor.
        :return: Meter model string
        """
        return self._data.get('nm_mrk')

    @property
    def today_indications(self) -> List[Optional[float]]:
        """
        Today indications accessor.
        Skims meter data for indications submitted today and prepares data.
        :return:
        """
        return [self._data.get('vl_%s_today' % i) for i in self.tariff_ids]

    @property
    def last_indications(self) -> List[Optional[float]]:
        """
        Last indications accessor.
        Returns data as list for indications submitted last.
        :return:
        """
        return [self._data.get('vl_%s_last_ind' % i) for i in self.tariff_ids]

    @property
    def last_indications_date(self) -> Optional[date]:
        if 'dt_last_ind' in self._data:
            return datetime.fromisoformat(self._data['dt_last_ind']).date()

    @property
    def invoice_indications(self) -> List[float]:
        return [self._data['vl_%s_inv' % i] for i in self.tariff_ids]

    @property
    def period_start_date(self) -> date:
        return DateUtil.moscow_today().replace(day=self._data['nn_period_start'])

    @property
    def period_end_date(self) -> date:
        return DateUtil.moscow_today().replace(day=self._data['nn_period_end'])

    @property
    def current_status(self):
        return self._data['nm_result']

    # Submission algorithms
    async def _prepare_indications_request(self, indications: IndicationsType):
        # noinspection PyTypeChecker
        account: MESAccount = self._account

        converter = float if await account.get_indications_is_float() else int

        request_dict = {
            'vl_%s' % tariff_id: converter(indication)
            for tariff_id, indication in zip(self.tariff_ids, indications)
            if indication is not None
        }

        request_dict['pr_flat_meter'] = self._data['pr_flat_meter']

        request_dict['nn_phone'] = await account.get_contact_phone()

        return request_dict

    async def _submit_indications(self, indications: IndicationsType) -> str:
        return await self._common_submit_indications(indications, 'bytProxy')

    async def _calculate_indications(self, indications: IndicationsType) -> 'ChargeCalculation':
        return await self._common_calculate_indications(indications, 'bytProxy')


class TKOIndicationMeter(BaseMeter):
    @property
    def submitted_indications(self) -> List[Optional[float]]:
        raise ActionNotSupportedException('Submitted indications not available')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meter_code = self.account_code

    @property
    def tariff_ids(self) -> List[str]:
        return sorted(self._data.keys())

    @property
    def tariffs(self) -> List[Tariff]:
        tariffs = []

        for key in self.tariff_ids:
            indication = self._data[key]
            tariff = Tariff(
                id=key,
                name=indication.get(Invoice.ATTRS.NAME),
                unit=indication.get(Invoice.ATTRS.UNIT),
                description=None,
                cost=indication.get(Invoice.ATTRS.COST)
            )
            tariffs.append(tariff)

        return tariffs

    @property
    def meter_code(self) -> str:
        return self._meter_code

    @property
    def last_indications(self) -> List[Optional[float]]:
        return [None if a['value'] is None else float(a['value']) for a in self._data.values()]

    @property
    def today_indications(self) -> List[float]:
        raise ActionNotSupportedException('MES+TKO meters do not support `today_indications`')

    @property
    def tariff_count(self) -> int:
        return len(self._data)


class MOEGenericMeter(SubmittableMeter):
    """ Mosenergosbyt meter class """

    @property
    def meter_code(self) -> str:
        return self._data['nm_counter']

    @property
    def tariff_ids(self) -> List[str]:
        return ['main']

    @property
    def tariffs(self) -> List[Tariff]:
        return [
            Tariff(
                id=self.tariff_ids[0],
                name=self._data.get('nm_service'),
                description=None,
                unit=self._data.get('nm_measure_unit'),
                cost=None
            )
        ]

    @property
    def submitted_indications(self) -> List[Optional[float]]:
        return [self.submitted_indication]

    @property
    def submitted_indication(self) -> Optional[float]:
        last_indications_date = self.last_indications_date

        if last_indications_date is not None:
            period_start_date = self.period_start_date
            period_end_date = self.period_end_date

            if not (period_start_date is None or period_end_date is None) \
                    and period_start_date <= last_indications_date <= period_end_date:
                return self.last_indication

            return self.today_indication

        return None

    @property
    def today_indications(self) -> List[Optional[float]]:
        """
        Today indications accessor.
        Skims meter data for indications submitted today and prepares data.
        :return:
        """
        return [self.today_indication]

    @property
    def today_indication(self) -> Optional[float]:
        if self.last_indications_date == DateUtil.moscow_today():
            return self.last_indication
        return None

    @property
    def last_indications(self) -> List[Optional[float]]:
        """
        Last indications accessor.
        Returns data as list for indications submitted last.
        :return:
        """
        return [self.last_indication]

    @property
    def last_indication(self) -> Optional[float]:
        return self._data.get('vl_last_indication')

    @property
    def last_indications_date(self) -> Optional[date]:
        last_indications_date = self._data.get('dt_last_indication')
        if last_indications_date:
            last_indications_date = str(last_indications_date).replace(' ', 'T', 1).rstrip('0').rstrip('.')
            return datetime.fromisoformat(last_indications_date).date()

    @property
    def invoice_indications(self) -> List[Optional[float]]:
        return [None]

    @property
    def current_status(self) -> Optional[str]:
        # return str(self._data['pr_state'])
        return None

    # Submission algorithms
    async def _prepare_indications_request(self, indication: Union[int, float]):
        converter = float if await self._account.get_indications_is_float() else int
        new_value = converter(indication)

        return {
            'dt_indication': datetime.now().isoformat(),
            'id_counter': self._data['id_counter'],
            'id_counter_zn': self._data['id_counter_zn'],
            'id_source': 15418,  # @TODO: request this value dynamically?
            'pr_skip_anomaly': 0,
            'pr_skip_err': 0,
            'vl_indication': new_value
        }

    async def _submit_indications(self, indications: IndicationsType) -> str:
        request_dict = await self._prepare_indications_request(next(iter(indications)))
        result = await self._account.direct_request('propagateMoeInd', 'AbonentSaveIndication', request_dict)

        result_data = result.get('data')
        if result_data:
            data = result_data[0]

            if result.get('success') and data['kd_result'] == ResponseCodes.RESPONSE_RESULT:
                return data['nm_result']

            if data['kd_result'] == 2:
                raise IndicationsCountException('Sent invalid indications count')

        error_code = result_data.get('err_code')
        error_text = result_data.get('err_text')

        _LOGGER.debug('Indications saving response data: %s' % result)

        raise MosenergosbytException(
            'API returned error (code: %s): %s' % error_code or 'unknown', error_text or 'no description'
        )

    async def _calculate_indications(self, indications: IndicationsType) -> 'ChargeCalculation':
        raise ActionNotSupportedException('Provider does not support indication calculation')


class KSGElectricityMeter(SubmittableMeter):
    @property
    def meter_code(self) -> str:
        return self._account.info['nn_meter'].strip()

    @property
    def model(self) -> Optional[str]:
        return self._account.info.get('nm_counter_brand')

    @property
    def install_date(self) -> Optional[date]:
        install_date = self._account.info.get('dt_meter_installation')
        if install_date:
            return datetime.fromisoformat(install_date).date()

    @property
    def last_indications_date(self) -> Optional[date]:
        indications_date = self.data.get('date')

        if indications_date:
            return indications_date.date()

    @property
    def today_indications(self) -> List[Optional[float]]:
        if self.last_indications_date == DateUtil.moscow_today():
            return self.last_indications

        return self._empty_indications_list

    @property
    def last_indications(self) -> List[Optional[float]]:
        indications = []

        for tariff_id in self.tariff_ids:
            value = self.data.get('meters', {}).get(tariff_id)
            indications.append(None if value is None else float(value))

        return indications

    async def _submit_indications(self, indications: IndicationsType) -> str:
        return await self._common_submit_indications(indications, 'ksgProxy')

    async def _calculate_indications(self, indications: IndicationsType) -> 'ChargeCalculation':
        return await self._common_calculate_indications(indications, 'ksgProxy')


class ChargeCalculation:
    def __init__(self, meter: 'BaseMeter', indications: IndicationsType, charged: float, comment: str,
                 period: Optional[date] = None, correct: Any = None):
        self._period: date = DateUtil.month_start() if period is None else period
        self._meter = meter
        self._indications = dict(zip(meter.tariff_ids, indications))

        self.charged = float(charged)
        self.comment = comment
        self.correct: Optional[bool] = None if correct is None else bool(correct)

    def __str__(self):
        return self.comment

    def __int__(self):
        return int(self.charged)

    def __float__(self):
        return self.charged

    def __repr__(self):
        return '<' + self._meter.__class__.__name__ + '.' + self.__class__.__name__ + '[' + str(self.charged) + ']>'

    @property
    def period(self) -> date:
        return self._period

    @property
    def meter(self) -> 'BaseMeter':
        return self._meter

    @property
    def indications(self) -> Dict[str, float]:
        return self._indications.copy()


class Invoice:
    INITIAL_BALANCE = 'initial_balance'
    ADJUSTMENTS = 'adjustments'
    TOTAL = 'total'
    TOTAL_NO_INSURANCE = 'total_no_insurance'

    class ATTRS:
        NAME = 'name'
        UNIT = 'unit'
        VALUE = 'value'
        COST = 'cost'
        CALCULATIONS = 'calculations'

    class COSTS:
        CHARGED = 'charged'
        INSURANCE = 'insurance'
        PENALTY = 'penalty'
        SERVICE = 'service'

    class DEDUCTIONS:
        BENEFITS = 'benefits'
        PAYMENTS = 'payments'

    def __init__(self, account: 'BaseAccount', invoice_id: str, period: date, charges: Dict[str, Dict[str, Any]],
                 calculations: Optional[Dict[str, float]] = None):
        self._account = account
        self._invoice_id = invoice_id
        self._period = period
        self._charges = charges
        self._calculations = calculations

    def _attribute_from_calculations(self, attribute: str) -> float:
        if self._calculations is not None and attribute in self._calculations:
            return self._calculations[attribute]
        return sum([c.get(self.ATTRS.CALCULATIONS, {}).get(attribute, 0) for c in self._charges.values()])

    @property
    def account(self) -> 'BaseAccount':
        return self._account

    @property
    def invoice_id(self) -> str:
        return self._invoice_id

    @property
    def period(self) -> date:
        return self._period

    @property
    def total(self) -> float:
        return self._attribute_from_calculations(self.TOTAL)

    @property
    def total_no_insurance(self) -> float:
        if self._calculations is not None:
            if self.TOTAL_NO_INSURANCE in self._calculations:
                return self._calculations[self.TOTAL_NO_INSURANCE]
            return self.total - self.insurance
        return 0

    @property
    def charged(self) -> float:
        return self._attribute_from_calculations(self.COSTS.CHARGED)

    @property
    def initial_balance(self) -> float:
        return self._attribute_from_calculations(self.INITIAL_BALANCE)

    @property
    def paid_amount(self) -> float:
        return self._attribute_from_calculations(self.DEDUCTIONS.PAYMENTS)

    @property
    def insurance(self) -> float:
        return 0 if self._calculations is None else self._calculations.get(self.COSTS.INSURANCE, 0)

    @property
    def benefits(self) -> float:
        return self._attribute_from_calculations(self.DEDUCTIONS.BENEFITS)

    @property
    def penalty(self) -> float:
        return self._attribute_from_calculations(self.COSTS.PENALTY)

    @property
    def service(self) -> float:
        return self._attribute_from_calculations(self.COSTS.SERVICE)


class MosenergosbytException(Exception):
    pass


class SubmissionPeriodException(MosenergosbytException):
    pass


class IndicationsCountException(MosenergosbytException):
    pass


class IndicationsThresholdException(MosenergosbytException):
    pass


class UnsupportedAccountException(MosenergosbytException):
    pass


class UnsupportedServiceException(UnsupportedAccountException):
    pass


class UnsupportedProviderException(UnsupportedAccountException):
    pass


class ActionNotSupportedException(MosenergosbytException):
    pass
