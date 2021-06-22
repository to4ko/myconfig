import attr
from homeassistant.const import ATTR_SERVICE

from custom_components.lkcomu_interrao.const import (
    ATTR_AGENT,
    ATTR_AMOUNT,
    ATTR_BENEFITS,
    ATTR_CHARGED,
    ATTR_DETAILS,
    ATTR_GROUP,
    ATTR_INITIAL,
    ATTR_INSURANCE,
    ATTR_INVOICE_ID,
    ATTR_PAID,
    ATTR_PAID_AT,
    ATTR_PENALTY,
    ATTR_PERIOD,
    ATTR_RECALCULATIONS,
    ATTR_STATUS,
    ATTR_TOTAL,
)
from inter_rao_energosbyt.interfaces import AbstractInvoice, AbstractPayment
from inter_rao_energosbyt.presets.byt import BytInvoice


def payment_to_attrs(payment: AbstractPayment):
    return {
        ATTR_AMOUNT: payment.amount,
        ATTR_PAID_AT: payment.paid_at.isoformat(),
        ATTR_STATUS: payment.status,
        ATTR_AGENT: payment.agent,
        ATTR_PERIOD: payment.period.isoformat(),
        ATTR_GROUP: payment.group_id,
    }


def invoice_to_attrs(invoice: AbstractInvoice):
    attributes = {
        ATTR_PERIOD: invoice.period.isoformat(),
        ATTR_INVOICE_ID: invoice.id,
        ATTR_TOTAL: invoice.total,
        ATTR_PAID: invoice.paid,
        ATTR_INITIAL: invoice.initial,
        ATTR_CHARGED: invoice.charged,
        ATTR_INSURANCE: invoice.insurance,
        ATTR_BENEFITS: invoice.benefits,
        ATTR_PENALTY: invoice.penalty,
        ATTR_SERVICE: invoice.service,
        ATTR_RECALCULATIONS: invoice.recalculations,
    }

    if isinstance(invoice, BytInvoice):
        attributes[ATTR_DETAILS] = list(map(attr.asdict, invoice.details))

    return attributes
