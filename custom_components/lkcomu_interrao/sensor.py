"""
Sensor for Inter RAO cabinet.
Retrieves indications regarding current state of accounts.
"""
import logging
import re
from datetime import date, datetime
from enum import IntEnum
from typing import (
    Any,
    ClassVar,
    Dict,
    Final,
    Hashable,
    Mapping,
    Optional,
    TypeVar,
    Union,
)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    CONF_DESCRIPTION,
    STATE_LOCKED,
    STATE_OK,
    STATE_PROBLEM,
    STATE_UNKNOWN,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from custom_components.lkcomu_interrao._base import (
    LkcomuInterRAOEntity,
    SupportedServicesType,
    make_common_async_setup_entry,
)
from custom_components.lkcomu_interrao._encoders import invoice_to_attrs, payment_to_attrs
from custom_components.lkcomu_interrao._util import with_auto_auth
from custom_components.lkcomu_interrao.const import (
    ATTR_ACCOUNT_CODE,
    ATTR_ACCOUNT_ID,
    ATTR_ADDRESS,
    ATTR_BENEFITS,
    ATTR_CALL_PARAMS,
    ATTR_CHARGED,
    ATTR_COMMENT,
    ATTR_DESCRIPTION,
    ATTR_END,
    ATTR_FULL_NAME,
    ATTR_IGNORE_INDICATIONS,
    ATTR_IGNORE_PERIOD,
    ATTR_INCREMENTAL,
    ATTR_INDICATIONS,
    ATTR_INITIAL,
    ATTR_INSTALL_DATE,
    ATTR_INSURANCE,
    ATTR_INVOICE_ID,
    ATTR_LAST_INDICATIONS_DATE,
    ATTR_LIVING_AREA,
    ATTR_METER_CATEGORY,
    ATTR_METER_CODE,
    ATTR_METER_MODEL,
    ATTR_MODEL,
    ATTR_NOTIFICATION,
    ATTR_PAID,
    ATTR_PENALTY,
    ATTR_PERIOD,
    ATTR_PREVIOUS,
    ATTR_PROVIDER_NAME,
    ATTR_PROVIDER_TYPE,
    ATTR_REASON,
    ATTR_REMAINING_DAYS,
    ATTR_RESULT,
    ATTR_SERVICE_NAME,
    ATTR_SERVICE_TYPE,
    ATTR_START,
    ATTR_STATUS,
    ATTR_SUBMIT_PERIOD_ACTIVE,
    ATTR_SUBMIT_PERIOD_END,
    ATTR_SUBMIT_PERIOD_START,
    ATTR_SUCCESS,
    ATTR_SUM,
    ATTR_TOTAL,
    ATTR_TOTAL_AREA,
    CONF_ACCOUNTS,
    CONF_DEV_PRESENTATION,
    CONF_LAST_INVOICE,
    CONF_LOGOS,
    CONF_METERS,
    DATA_PROVIDER_LOGOS,
    DOMAIN,
    FORMAT_VAR_ID,
    FORMAT_VAR_TYPE_EN,
    FORMAT_VAR_TYPE_RU,
)
from inter_rao_energosbyt.exceptions import EnergosbytException
from inter_rao_energosbyt.interfaces import (
    AbstractAccountWithBalance,
    AbstractAccountWithInvoices,
    AbstractAccountWithMeters,
    AbstractAccountWithPayments,
    AbstractBalance,
    AbstractCalculatableMeter,
    AbstractInvoice,
    AbstractMeter,
    AbstractSubmittableMeter,
    Account,
)
from inter_rao_energosbyt.presets.byt import AccountWithBytInfo, BytInfoSingle
from inter_rao_energosbyt.util import process_start_end_arguments

_LOGGER = logging.getLogger(__name__)

RE_HTML_TAGS = re.compile(r"<[^<]+?>")
RE_MULTI_SPACES = re.compile(r"\s{2,}")

INDICATIONS_MAPPING_SCHEMA = vol.Schema(
    {
        vol.Required(vol.Match(r"t\d+")): cv.positive_float,
    }
)

INDICATIONS_SEQUENCE_SCHEMA = vol.All(
    vol.Any(vol.All(cv.positive_float, cv.ensure_list), [cv.positive_float]),
    lambda x: dict(map(lambda y: ("t" + str(y[0]), y[1]), enumerate(x, start=1))),
)


CALCULATE_PUSH_INDICATIONS_SCHEMA = {
    vol.Required(ATTR_INDICATIONS): vol.Any(
        vol.All(
            cv.string, lambda x: list(map(str.strip, x.split(","))), INDICATIONS_SEQUENCE_SCHEMA
        ),
        INDICATIONS_MAPPING_SCHEMA,
        INDICATIONS_SEQUENCE_SCHEMA,
    ),
    vol.Optional(ATTR_IGNORE_PERIOD, default=False): cv.boolean,
    vol.Optional(ATTR_IGNORE_INDICATIONS, default=False): cv.boolean,
    vol.Optional(ATTR_INCREMENTAL, default=False): cv.boolean,
    vol.Optional(ATTR_NOTIFICATION, default=False): vol.Any(
        cv.boolean,
        persistent_notification.SCHEMA_SERVICE_CREATE,
    ),
}

SERVICE_PUSH_INDICATIONS: Final = "push_indications"
SERVICE_PUSH_INDICATIONS_SCHEMA: Final = CALCULATE_PUSH_INDICATIONS_SCHEMA

SERVICE_CALCULATE_INDICATIONS: Final = "calculate_indications"
SERVICE_CALCULATE_INDICATIONS_SCHEMA: Final = CALCULATE_PUSH_INDICATIONS_SCHEMA

_SERVICE_SCHEMA_BASE_DATED: Final = {
    vol.Optional(ATTR_START, default=None): vol.Any(vol.Equal(None), cv.datetime),
    vol.Optional(ATTR_END, default=None): vol.Any(vol.Equal(None), cv.datetime),
}

FEATURE_PUSH_INDICATIONS: Final = 1
FEATURE_CALCULATE_INDICATIONS: Final = FEATURE_PUSH_INDICATIONS * 2
FEATURE_GET_PAYMENTS: Final = FEATURE_CALCULATE_INDICATIONS * 2
FEATURE_GET_INVOICES: Final = FEATURE_GET_PAYMENTS * 2

SERVICE_SET_DESCRIPTION: Final = "set_description"
SERVICE_GET_PAYMENTS: Final = "get_payments"
SERVICE_GET_INVOICES: Final = "get_invoices"

_TLkcomuInterRAOEntity = TypeVar("_TLkcomuInterRAOEntity", bound=LkcomuInterRAOEntity)


def get_supported_features(from_services: SupportedServicesType, for_object: Any) -> int:
    features = 0
    for type_feature, services in from_services.items():
        if type_feature is None:
            continue
        check_cls, feature = type_feature
        if isinstance(for_object, check_cls):
            features |= feature

    return features


class LkcomuAccount(LkcomuInterRAOEntity[Account]):
    """The class for this sensor"""

    config_key: ClassVar[str] = CONF_ACCOUNTS

    _supported_services: ClassVar[SupportedServicesType] = {
        None: {
            "set_description": {
                vol.Optional(CONF_DESCRIPTION): vol.Any(vol.Equal(None), cv.string),
            },
        },
        (AbstractAccountWithInvoices, FEATURE_GET_INVOICES): {
            "get_invoices": _SERVICE_SCHEMA_BASE_DATED,
        },
        (AbstractAccountWithPayments, FEATURE_GET_PAYMENTS): {
            "get_payments": _SERVICE_SCHEMA_BASE_DATED,
        },
    }

    def __init__(self, *args, balance: Optional[AbstractBalance] = None, **kwargs) -> None:
        super().__init__(*args, *kwargs)
        self._balance = balance

        self.entity_id: Optional[str] = f"sensor." + slugify(
            f"{self.account_provider_code or 'unknown'}_{self._account.code}_account"
        )

    @property
    def entity_picture(self) -> Optional[str]:
        if not self._account_config[CONF_LOGOS]:
            return None

        logos = self.hass.data.get(DATA_PROVIDER_LOGOS)
        if not logos:
            return None

        account_provider_code = self.account_provider_code
        if account_provider_code is None:
            return None

        provider_logo = logos.get(account_provider_code)
        if isinstance(provider_logo, str):
            return provider_logo

        return None

    @property
    def code(self) -> str:
        return self._account.code

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_account"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        acc = self._account
        return f"{acc.api.__class__.__name__}_account_{acc.id}"

    @property
    def state(self) -> Union[str, float]:
        if self._account.is_locked:
            return STATE_PROBLEM
        balance = self._balance
        if balance is not None:
            if self._account_config[CONF_DEV_PRESENTATION]:
                return ("-" if (balance.balance or 0.0) < 0.0 else "") + "#####.###"
            return round(balance.balance or 0.0, 2)  # fixes -0.0 issues
        return STATE_UNKNOWN

    @property
    def icon(self) -> str:
        return "mdi:flash-circle"

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return "руб."

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        account = self._account
        service_type_value = account.service_type
        service_type = (
            service_type_value.name.lower()
            if isinstance(service_type_value, IntEnum)
            else str(service_type_value)
        )

        provider_type_value = account.provider_type
        provider_type = (
            provider_type_value.name.lower()
            if isinstance(provider_type_value, IntEnum)
            else str(provider_type_value)
        )

        attributes = {
            ATTR_ADDRESS: account.address,
            ATTR_DESCRIPTION: account.description,
            ATTR_PROVIDER_TYPE: provider_type,
            ATTR_PROVIDER_NAME: account.provider_name,
            ATTR_SERVICE_TYPE: service_type,
            ATTR_SERVICE_NAME: account.service_name,
        }

        if account.is_locked:
            attributes[ATTR_STATUS] = STATE_LOCKED
            attributes[ATTR_REASON] = account.lock_reason

        else:
            attributes[ATTR_STATUS] = STATE_OK

        if isinstance(account, AccountWithBytInfo):
            info = account.info
            if info:
                attributes.update(
                    {
                        ATTR_FULL_NAME: info.full_name,
                        ATTR_LIVING_AREA: info.living_area,
                        ATTR_TOTAL_AREA: info.total_area,
                        ATTR_METER_CATEGORY: info.meter_category,
                        ATTR_METER_CODE: info.meter_code,
                    }
                )

                zones = account.info.zones
                if zones is not None:
                    for zone_id, zone_def in zones.items():
                        attrs = ("name", "description", "tariff")
                        for prefix in ("", "within_"):
                            values = tuple(getattr(zone_def, prefix + attr) for attr in attrs)
                            if any(values):
                                attributes.update(
                                    zip(
                                        map(lambda x: f"zone_{zone_id}_{prefix}{x}", attrs),
                                        values,
                                    )
                                )

                if isinstance(info, BytInfoSingle):
                    attributes[ATTR_METER_MODEL] = info.meter_model

        self._handle_dev_presentation(
            attributes,
            (),
            (
                ATTR_DESCRIPTION,
                ATTR_FULL_NAME,
                ATTR_ADDRESS,
                ATTR_LIVING_AREA,
                ATTR_TOTAL_AREA,
                ATTR_METER_MODEL,
                ATTR_METER_CODE,
            ),
        )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        """Return the name of the sensor"""
        account = self._account
        return {
            FORMAT_VAR_ID: str(account.id),
            FORMAT_VAR_TYPE_EN: "account",
            FORMAT_VAR_TYPE_RU: "лицевой счёт",
        }

    #################################################################################
    # Functional implementation of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_accounts(
        cls,
        entities: Dict[Hashable, _TLkcomuInterRAOEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ):
        entity_key = account.id
        try:
            entity = entities[entity_key]
        except KeyError:
            entity = cls(account, account_config)
            entities[entity_key] = entity

            return [entity]
        else:
            if entity.enabled:
                entity.async_schedule_update_ha_state(force_refresh=True)

    async def async_update_internal(self) -> None:
        await self._account.async_update_related()
        account = self._account

        if isinstance(account, AbstractAccountWithBalance):
            self._balance = await account.async_get_balance()

        if isinstance(account, AccountWithBytInfo):
            await account.async_update_info()

        self.register_supported_services(account)

    #################################################################################
    # Services callbacks
    #################################################################################

    @property
    def supported_features(self) -> int:
        return get_supported_features(
            self._supported_services,
            self._account,
        )

    async def async_service_get_payments(self, **call_data):
        account = self._account

        _LOGGER.info(self.log_prefix + "Begin handling payments retrieval")

        if not isinstance(account, AbstractAccountWithPayments):
            raise ValueError("account does not support payments retrieval")

        dt_start: Optional["datetime"] = call_data[ATTR_START]
        dt_end: Optional["datetime"] = call_data[ATTR_END]

        dt_start, dt_end = process_start_end_arguments(dt_start, dt_end)
        results = []

        event_data = {
            ATTR_ACCOUNT_CODE: account.code,
            ATTR_ACCOUNT_ID: account.id,
            ATTR_SUCCESS: False,
            ATTR_START: dt_start.isoformat(),
            ATTR_END: dt_end.isoformat(),
            ATTR_RESULT: results,
            ATTR_COMMENT: None,
            ATTR_SUM: 0.0,
        }

        try:
            payments = await with_auto_auth(
                account.api,
                account.async_get_payments,
                dt_start,
                dt_end,
            )

            for payment in payments:
                event_data[ATTR_SUM] += payment.amount
                results.append(payment_to_attrs(payment))

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.exception(event_data[ATTR_COMMENT])
            raise
        else:
            event_data[ATTR_SUCCESS] = True

        finally:
            self.hass.bus.async_fire(
                event_type=DOMAIN + "_" + SERVICE_GET_PAYMENTS,
                event_data=event_data,
            )

            _LOGGER.info(self.log_prefix + "Finish handling payments retrieval")

    async def async_service_get_invoices(self, **call_data):
        account = self._account

        _LOGGER.info(self.log_prefix + "Begin handling invoices retrieval")

        if not isinstance(account, AbstractAccountWithInvoices):
            raise ValueError("account does not support invoices retrieval")

        dt_start: Optional["datetime"] = call_data[ATTR_START]
        dt_end: Optional["datetime"] = call_data[ATTR_END]

        dt_start, dt_end = process_start_end_arguments(dt_start, dt_end)
        results = []

        event_data = {
            ATTR_ACCOUNT_CODE: account.code,
            ATTR_ACCOUNT_ID: account.id,
            ATTR_SUCCESS: False,
            ATTR_START: dt_start.isoformat(),
            ATTR_END: dt_end.isoformat(),
            ATTR_RESULT: results,
            ATTR_COMMENT: None,
            ATTR_SUM: 0.0,
        }

        try:
            invoices = await with_auto_auth(
                account.api,
                account.async_get_invoices,
                dt_start,
                dt_end,
            )

            for invoice in invoices:
                event_data[ATTR_SUM] += invoice.total
                results.append(invoice_to_attrs(invoice))

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.exception(event_data[ATTR_COMMENT])
            raise
        else:
            event_data[ATTR_SUCCESS] = True

        finally:
            self.hass.bus.async_fire(
                event_type=DOMAIN + "_" + SERVICE_GET_INVOICES,
                event_data=event_data,
            )

            _LOGGER.info(self.log_prefix + "Finish handling invoices retrieval")

    async def async_service_set_description(self, **call_data):
        account = self._account

        _LOGGER.info(self.log_prefix + "Begin handling description setting")

        event_data = {
            ATTR_ACCOUNT_CODE: account.code,
            ATTR_ACCOUNT_ID: account.id,
            ATTR_SUCCESS: False,
            ATTR_DESCRIPTION: call_data.get(CONF_DESCRIPTION),
            ATTR_PREVIOUS: account.description,
        }

        try:
            await with_auto_auth(
                account.api,
                account.async_set_description,
                description=event_data[ATTR_DESCRIPTION],
                update=False,
            )

        except EnergosbytException as e:
            event_data[ATTR_COMMENT] = "Error: %s" % e
            raise

        except Exception as e:
            event_data[ATTR_COMMENT] = "Unknown error: %s" % e
            _LOGGER.exception("Unknown error: %s", e)
            raise

        else:
            event_data[ATTR_COMMENT] = "Successful calculation"
            event_data[ATTR_SUCCESS] = True
            self.async_schedule_update_ha_state(force_refresh=True)

        finally:
            self.hass.bus.async_fire(
                event_type=DOMAIN + "_" + SERVICE_SET_DESCRIPTION,
                event_data=event_data,
            )

            _LOGGER.info(self.log_prefix + "End handling indications calculation")


class LkcomuMeter(LkcomuInterRAOEntity[AbstractAccountWithMeters]):
    """The class for this sensor"""

    config_key: ClassVar[str] = CONF_METERS

    _supported_services: ClassVar[SupportedServicesType] = {
        (AbstractSubmittableMeter, FEATURE_PUSH_INDICATIONS): {
            "push_indications": SERVICE_PUSH_INDICATIONS_SCHEMA,
        },
        (AbstractCalculatableMeter, FEATURE_CALCULATE_INDICATIONS): {
            "calculate_indications": SERVICE_PUSH_INDICATIONS_SCHEMA,
        },
    }

    def __init__(self, *args, meter: AbstractMeter, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._meter = meter

        self.entity_id: Optional[str] = f"sensor." + slugify(
            f"{self.account_provider_code or 'unknown'}_{self._account.code}_meter_{self.code}"
        )

    #################################################################################
    # Implementation base of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_accounts(
        cls,
        entities: Dict[Hashable, Optional[_TLkcomuInterRAOEntity]],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ):
        new_meter_entities = []
        if isinstance(account, AbstractAccountWithMeters):
            meters = await account.async_get_meters()

            for meter_id, meter in meters.items():
                entity_key = (account.id, meter_id)
                try:
                    entity = entities[entity_key]
                except KeyError:
                    entity = cls(
                        account,
                        account_config,
                        meter=meter,
                    )
                    entities[entity_key] = entity
                    new_meter_entities.append(entity)
                else:
                    if entity.enabled:
                        entity.async_schedule_update_ha_state(force_refresh=True)

        return new_meter_entities if new_meter_entities else None

    async def async_update_internal(self) -> None:
        meters = await self._account.async_get_meters()
        meter = meters.get(self._meter.id)
        if meter is None:
            self.hass.async_create_task(self.async_remove())
        else:
            self.register_supported_services(meter)

            self._meter = meter

    #################################################################################
    # Data-oriented implementation of inherent class
    #################################################################################

    @property
    def code(self) -> str:
        return self._meter.code

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        met = self._meter
        acc = met.account
        return f"{acc.api.__class__.__name__}_meter_{acc.id}_{met.id}"

    @property
    def state(self) -> str:
        return self._meter.status or STATE_OK

    @property
    def icon(self):
        return "mdi:counter"

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_meter"

    @property
    def supported_features(self) -> int:
        meter = self._meter
        return (
            isinstance(meter, AbstractSubmittableMeter) * FEATURE_PUSH_INDICATIONS
            | isinstance(meter, AbstractCalculatableMeter) * FEATURE_CALCULATE_INDICATIONS
        )

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        met = self._meter
        attributes = {
            ATTR_METER_CODE: met.code,
            ATTR_ACCOUNT_CODE: met.account.code,
        }

        # Meter model attribute
        model = met.model
        if model:
            attributes[ATTR_MODEL] = model

        # Installation date attribute
        install_date = met.installation_date
        if install_date:
            attributes[ATTR_INSTALL_DATE] = install_date.isoformat()

        # Submission periods attributes
        is_submittable = False
        if isinstance(met, AbstractSubmittableMeter):
            is_submittable = True  # this weird hack calms my IDE

            # noinspection PyUnresolvedReferences
            today = date.today()
            start_date, end_date = met.submission_period
            attributes[ATTR_SUBMIT_PERIOD_START] = start_date.isoformat()
            attributes[ATTR_SUBMIT_PERIOD_END] = end_date.isoformat()
            attributes[ATTR_SUBMIT_PERIOD_ACTIVE] = start_date <= today <= end_date

            if date.today() >= end_date:
                remaining_days = 0
            elif date.today() >= start_date:
                remaining_days = (end_date - today).days
            else:
                remaining_days = (start_date - today).days

            attributes[ATTR_REMAINING_DAYS] = remaining_days

        last_indications_date = met.last_indications_date
        attributes[ATTR_LAST_INDICATIONS_DATE] = (
            None if last_indications_date is None else last_indications_date.isoformat()
        )

        # Add zone information
        for zone_id, zone_def in met.zones.items():
            iterator = [
                ("name", zone_def.name),
                ("last_indication", zone_def.last_indication or 0.0),
                ("today_indication", zone_def.today_indication),
            ]

            if is_submittable:
                submitted_indication = zone_def.today_indication
                if submitted_indication is None and last_indications_date is not None:
                    # noinspection PyUnboundLocalVariable
                    if start_date <= last_indications_date <= end_date:
                        submitted_indication = zone_def.last_indication or 0.0
                iterator.append(("period_indication", submitted_indication))

            for attribute, value in iterator:
                attributes[f"zone_{zone_id}_{attribute}"] = value

        self._handle_dev_presentation(
            attributes,
            (),
            (
                ATTR_METER_CODE,
                ATTR_INSTALL_DATE,
                ATTR_LAST_INDICATIONS_DATE,
                *filter(lambda x: x.endswith("_indication"), attributes.keys()),
            ),
        )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        meter = self._meter
        return {
            FORMAT_VAR_ID: meter.id or "<unknown>",
            FORMAT_VAR_TYPE_EN: "meter",
            FORMAT_VAR_TYPE_RU: "счётчик",
        }

    #################################################################################
    # Additional functionality
    #################################################################################

    def _fire_callback_event(
        self, call_data: Mapping[str, Any], event_data: Mapping[str, Any], event_id: str, title: str
    ):
        meter = self._meter
        hass = self.hass
        comment = event_data.get(ATTR_COMMENT)

        if comment is not None:
            message = str(comment)
            comment = "Response comment: " + str(comment)
        else:
            comment = "Response comment not provided"
            message = comment

        _LOGGER.log(
            logging.INFO if event_data.get(ATTR_SUCCESS) else logging.ERROR,
            RE_MULTI_SPACES.sub(" ", RE_HTML_TAGS.sub("", comment)),
        )

        meter_code = meter.code

        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_METER_CODE: meter_code,
            ATTR_CALL_PARAMS: dict(call_data),
            ATTR_SUCCESS: False,
            ATTR_INDICATIONS: None,
            ATTR_COMMENT: None,
            **event_data,
        }

        _LOGGER.debug("Firing event '%s' with post_fields: %s" % (event_id, event_data))

        hass.bus.async_fire(event_type=event_id, event_data=event_data)

        notification_content: Union[bool, Mapping[str, str]] = call_data[ATTR_NOTIFICATION]

        if notification_content is not False:
            payload = {
                persistent_notification.ATTR_TITLE: title + " - №" + meter_code,
                persistent_notification.ATTR_NOTIFICATION_ID: event_id + "_" + meter_code,
                persistent_notification.ATTR_MESSAGE: message,
            }

            if isinstance(notification_content, Mapping):
                for key, value in notification_content.items():
                    payload[key] = str(value).format_map(event_data)

            hass.async_create_task(
                hass.services.async_call(
                    persistent_notification.DOMAIN,
                    persistent_notification.SERVICE_CREATE,
                    payload,
                )
            )

    def _get_real_indications(self, call_data: Mapping) -> Mapping[str, Union[int, float]]:
        indications: Mapping[str, Union[int, float]] = call_data[ATTR_INDICATIONS]
        meter_zones = self._meter.zones

        for zone_id, new_value in indications.items():
            if zone_id not in meter_zones:
                raise ValueError(f"meter zone {zone_id} does not exist")

        if call_data[ATTR_INCREMENTAL]:
            return {
                zone_id: (
                    (
                        meter_zones[zone_id].today_indication
                        or meter_zones[zone_id].last_indication
                        or 0
                    )
                    + new_value
                )
                for zone_id, new_value in indications.items()
            }

        return indications

    async def async_service_push_indications(self, **call_data):
        """
        Push indications entity service.
        :param call_data: Parameters for service call
        :return:
        """
        _LOGGER.info(self.log_prefix + "Begin handling indications submission")

        meter = self._meter

        if meter is None:
            raise Exception("Meter is unavailable")

        meter_code = meter.code

        if not isinstance(meter, AbstractSubmittableMeter):
            raise Exception("Meter '%s' does not support indications submission" % (meter_code,))

        else:
            event_data = {}

            try:
                indications = self._get_real_indications(call_data)

                event_data[ATTR_INDICATIONS] = dict(indications)

                await with_auto_auth(
                    meter.account.api,
                    meter.async_submit_indications,
                    **indications,
                    ignore_periods=call_data[ATTR_IGNORE_PERIOD],
                    ignore_values=call_data[ATTR_IGNORE_INDICATIONS],
                )

            except EnergosbytException as e:
                event_data[ATTR_COMMENT] = "API error: %s" % e
                raise

            except BaseException as e:
                event_data[ATTR_COMMENT] = "Unknown error: %r" % e
                _LOGGER.error(event_data[ATTR_COMMENT])
                raise

            else:
                event_data[ATTR_COMMENT] = "Indications submitted successfully"
                event_data[ATTR_SUCCESS] = True
                self.async_schedule_update_ha_state(force_refresh=True)

            finally:
                self._fire_callback_event(
                    call_data,
                    event_data,
                    DOMAIN + "_" + SERVICE_PUSH_INDICATIONS,
                    "Передача показаний",
                )

                _LOGGER.info(self.log_prefix + "End handling indications submission")

    async def async_service_calculate_indications(self, **call_data):
        meter = self._meter

        if meter is None:
            raise Exception("Meter is unavailable")

        meter_code = meter.code

        _LOGGER.info(self.log_prefix + "Begin handling indications calculation")

        if not isinstance(meter, AbstractCalculatableMeter):
            raise Exception("Meter '%s' does not support indications calculation" % (meter_code,))

        event_data = {ATTR_CHARGED: None, ATTR_SUCCESS: False}

        try:
            indications = self._get_real_indications(call_data)

            event_data[ATTR_INDICATIONS] = dict(indications)

            calculation = await with_auto_auth(
                meter.account.api,
                meter.async_calculate_indications,
                **indications,
                ignore_periods=call_data[ATTR_IGNORE_PERIOD],
                ignore_values=call_data[ATTR_IGNORE_INDICATIONS],
            )

        except EnergosbytException as e:
            event_data[ATTR_COMMENT] = "Error: %s" % e
            raise

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.exception(event_data[ATTR_COMMENT])
            raise

        else:
            event_data[ATTR_CHARGED] = float(calculation)
            event_data[ATTR_COMMENT] = "Successful calculation"
            event_data[ATTR_SUCCESS] = True

            self.async_schedule_update_ha_state(force_refresh=True)

        finally:
            self._fire_callback_event(
                call_data,
                event_data,
                DOMAIN + "_" + SERVICE_CALCULATE_INDICATIONS,
                "Подсчёт показаний",
            )

            _LOGGER.info(self.log_prefix + "End handling indications calculation")


class LkcomuLastInvoice(LkcomuInterRAOEntity[AbstractAccountWithInvoices]):
    config_key = CONF_LAST_INVOICE

    def __init__(self, *args, last_invoice: Optional["AbstractInvoice"] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_invoice = last_invoice

        self.entity_id: Optional[str] = "sensor." + slugify(
            f"{self.account_provider_code or 'unknown'}_{self._account.code}_last_invoice"
        )

    @property
    def code(self) -> str:
        return self._account.code

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_invoice"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        acc = self._account
        return f"{acc.api.__class__.__name__}_lastinvoice_{acc.id}"

    @property
    def state(self) -> Union[float, str]:
        invoice = self._last_invoice
        if invoice:
            if self._account_config[CONF_DEV_PRESENTATION]:
                return ("-" if (invoice.total or 0.0) < 0.0 else "") + "#####.###"
            return round(invoice.total or 0.0, 2)
        return STATE_UNKNOWN

    @property
    def icon(self) -> str:
        return "mdi:receipt"

    @property
    def unit_of_measurement(self) -> str:
        return "руб." if self._last_invoice else None

    @property
    def sensor_related_attributes(self):
        invoice = self._last_invoice

        if invoice:
            attributes = invoice_to_attrs(invoice)

            self._handle_dev_presentation(
                attributes,
                (ATTR_PERIOD, ATTR_INVOICE_ID),
                (
                    ATTR_TOTAL,
                    ATTR_PAID,
                    ATTR_INITIAL,
                    ATTR_CHARGED,
                    ATTR_INSURANCE,
                    ATTR_BENEFITS,
                    ATTR_PENALTY,
                    ATTR_SERVICE,
                ),
            )

            return attributes

        return {}

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        invoice = self._last_invoice
        return {
            FORMAT_VAR_ID: invoice.id if invoice else "<?>",
            FORMAT_VAR_TYPE_EN: "last invoice",
            FORMAT_VAR_TYPE_RU: "последняя квитанция",
        }

    @classmethod
    async def async_refresh_accounts(
        cls,
        entities: Dict[Hashable, _TLkcomuInterRAOEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ):
        entity_key = account.id
        if isinstance(account, AbstractAccountWithInvoices):
            try:
                entity = entities[entity_key]
            except KeyError:
                entity = cls(account, account_config)
                entities[entity_key] = entity
                return [entity]
            else:
                if entity.enabled:
                    await entity.async_update_ha_state(force_refresh=True)

        return None

    async def async_update_internal(self) -> None:
        self._last_invoice = await self._account.async_get_last_invoice()


async_setup_entry = make_common_async_setup_entry(
    LkcomuAccount,
    LkcomuLastInvoice,
    LkcomuMeter,
)
