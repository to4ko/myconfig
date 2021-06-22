from typing import Any, ClassVar, Dict, Hashable, Iterable, Mapping, Optional, Type, TypeVar

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util import slugify

from custom_components.lkcomu_interrao._base import (
    LkcomuInterRAOEntity,
    make_common_async_setup_entry,
)
from custom_components.lkcomu_interrao._encoders import payment_to_attrs
from custom_components.lkcomu_interrao.const import (
    ATTR_AGENT,
    ATTR_AMOUNT,
    ATTR_GROUP,
    ATTR_PAID_AT,
    ATTR_PERIOD,
    CONF_LAST_PAYMENT,
    DOMAIN,
    FORMAT_VAR_ID,
    FORMAT_VAR_TYPE_EN,
    FORMAT_VAR_TYPE_RU,
)
from inter_rao_energosbyt.interfaces import AbstractAccountWithPayments, AbstractPayment, Account

_TLkcomuInterRAOEntity = TypeVar("_TLkcomuInterRAOEntity", bound=LkcomuInterRAOEntity)


class LkcomuInterRAOLastPayment(
    LkcomuInterRAOEntity[AbstractAccountWithPayments], BinarySensorEntity
):
    config_key: ClassVar[str] = CONF_LAST_PAYMENT

    def __init__(self, *args, last_payment: Optional[AbstractPayment] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_payment = last_payment

        self._entity_id: Optional[str] = f"binary_sensor." + slugify(
            f"{self.account_provider_code or 'unknown'}_{self._account.code}_last_payment"
        )

    @property
    def is_on(self) -> bool:
        payment = self._last_payment
        return payment is not None and payment.is_accepted

    @property
    def entity_id(self) -> Optional[str]:
        return self._entity_id

    @entity_id.setter
    def entity_id(self, value: Optional[str]) -> None:
        self._entity_id = value

    #################################################################################
    # Implementation base of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_accounts(
        cls: Type[_TLkcomuInterRAOEntity],
        entities: Dict[Hashable, _TLkcomuInterRAOEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ) -> Optional[Iterable[_TLkcomuInterRAOEntity]]:
        if isinstance(account, AbstractAccountWithPayments):
            entity_key = account.id

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
        self._last_payment = await self._account.async_get_last_payment()

    #################################################################################
    # Data-oriented implementation of inherent class
    #################################################################################

    @property
    def code(self) -> str:
        return self._account.code

    @property
    def state(self) -> StateType:
        data = self._last_payment

        if data is None:
            return STATE_UNKNOWN

        return STATE_ON if self.is_on else STATE_OFF

    @property
    def icon(self) -> str:
        return "mdi:cash-multiple"

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        payment = self._last_payment

        if payment is None:
            attributes = {}
        else:

            attributes = payment_to_attrs(payment)
            self._handle_dev_presentation(
                attributes, (ATTR_PAID_AT, ATTR_PERIOD), (ATTR_AMOUNT, ATTR_AGENT, ATTR_GROUP)
            )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        last_payment = self._last_payment
        return {
            FORMAT_VAR_ID: last_payment.id if last_payment else "<?>",
            FORMAT_VAR_TYPE_EN: "last payment",
            FORMAT_VAR_TYPE_RU: "последний платёж",
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        acc = self._account
        return f"{acc.api.__class__.__name__}_lastpayment_{acc.id}"

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_payment"


async_setup_entry = make_common_async_setup_entry(LkcomuInterRAOLastPayment)
