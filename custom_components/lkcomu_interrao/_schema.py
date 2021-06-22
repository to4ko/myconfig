__all__ = ("CONFIG_ENTRY_SCHEMA",)

from datetime import timedelta
from typing import Any, Hashable, Mapping, Optional

import voluptuous as vol
from homeassistant.const import (
    CONF_DEFAULT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

from custom_components.lkcomu_interrao._util import IS_IN_RUSSIA
from custom_components.lkcomu_interrao.const import (
    API_TYPE_DEFAULT,
    API_TYPE_NAMES,
    CONF_ACCOUNTS,
    CONF_DEV_PRESENTATION,
    CONF_LAST_INVOICE,
    CONF_LAST_PAYMENT,
    CONF_LOGOS,
    CONF_METERS,
    CONF_NAME_FORMAT,
    CONF_USER_AGENT,
    DEFAULT_NAME_FORMAT_EN_ACCOUNTS,
    DEFAULT_NAME_FORMAT_EN_LAST_INVOICE,
    DEFAULT_NAME_FORMAT_EN_LAST_PAYMENT,
    DEFAULT_NAME_FORMAT_EN_METERS,
    DEFAULT_NAME_FORMAT_RU_ACCOUNTS,
    DEFAULT_NAME_FORMAT_RU_LAST_INVOICE,
    DEFAULT_NAME_FORMAT_RU_LAST_PAYMENT,
    DEFAULT_NAME_FORMAT_RU_METERS,
    DEFAULT_SCAN_INTERVAL,
)

MIN_SCAN_INTERVAL = timedelta(seconds=60)


(
    default_name_format_accounts,
    default_name_format_last_invoice,
    default_name_format_meters,
    default_name_format_last_payment,
) = (
    (
        DEFAULT_NAME_FORMAT_RU_ACCOUNTS,
        DEFAULT_NAME_FORMAT_RU_LAST_INVOICE,
        DEFAULT_NAME_FORMAT_RU_METERS,
        DEFAULT_NAME_FORMAT_RU_LAST_PAYMENT,
    )
    if IS_IN_RUSSIA
    else (
        DEFAULT_NAME_FORMAT_EN_ACCOUNTS,
        DEFAULT_NAME_FORMAT_EN_LAST_INVOICE,
        DEFAULT_NAME_FORMAT_EN_METERS,
        DEFAULT_NAME_FORMAT_EN_LAST_PAYMENT,
    )
)


NAME_FORMAT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCOUNTS, default=default_name_format_accounts): cv.string,
        vol.Optional(CONF_LAST_INVOICE, default=default_name_format_last_invoice): cv.string,
        vol.Optional(CONF_METERS, default=default_name_format_meters): cv.string,
        vol.Optional(CONF_LAST_PAYMENT, default=default_name_format_last_payment): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


SCAN_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCOUNTS, default=DEFAULT_SCAN_INTERVAL): cv.positive_time_period,
        vol.Optional(CONF_LAST_INVOICE, default=DEFAULT_SCAN_INTERVAL): cv.positive_time_period,
        vol.Optional(CONF_METERS, default=DEFAULT_SCAN_INTERVAL): cv.positive_time_period,
        vol.Optional(CONF_LAST_PAYMENT, default=DEFAULT_SCAN_INTERVAL): cv.positive_time_period,
    }
)


def _validator_name_format_schema(schema):
    return vol.Any(
        vol.All(cv.string, lambda x: {CONF_ACCOUNTS: x}, schema),
        schema,
    )


GENERIC_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCOUNTS, default=True): cv.boolean,
        vol.Optional(CONF_LAST_INVOICE, default=True): cv.boolean,
        vol.Optional(CONF_METERS, default=True): cv.boolean,
        vol.Optional(CONF_LAST_PAYMENT, default=True): cv.boolean,
        vol.Optional(CONF_LOGOS, default=True): cv.boolean,
        vol.Optional(CONF_DEV_PRESENTATION, default=False): cv.boolean,
        vol.Optional(CONF_NAME_FORMAT, default=lambda: NAME_FORMAT_SCHEMA({})): vol.Any(
            vol.All(cv.string, lambda x: {CONF_ACCOUNTS: x}, NAME_FORMAT_SCHEMA),
            NAME_FORMAT_SCHEMA,
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=lambda: SCAN_INTERVAL_SCHEMA({})): vol.Any(
            vol.All(
                cv.positive_time_period,
                lambda x: dict.fromkeys(
                    (CONF_ACCOUNTS, CONF_LAST_INVOICE, CONF_METERS, CONF_LAST_PAYMENT), x
                ),
                SCAN_INTERVAL_SCHEMA,
            ),
            SCAN_INTERVAL_SCHEMA,
        ),
    },
    extra=vol.PREVENT_EXTRA,
)


def _make_account_validator(account_schema):
    return vol.Any(
        vol.Equal(False),  # For disabling
        vol.All(vol.Equal(True), lambda _: account_schema({})),  # For default
        account_schema,  # For custom
    )


GENERIC_ACCOUNT_VALIDATOR = _make_account_validator(GENERIC_ACCOUNT_SCHEMA)


def _make_provider_schema(
    provider_type: str,
    add_to_config: Optional[Mapping[Hashable, Any]] = None,
    add_to_accounts: Optional[Mapping[Hashable, Any]] = None,
):
    if provider_type not in API_TYPE_NAMES:
        raise ValueError(f"api '{provider_type}' is not defined")

    add_to_config = {} if add_to_config is None else dict(add_to_config)
    add_to_config[vol.Required(CONF_TYPE)] = vol.Equal(provider_type)

    if add_to_accounts:
        accounts_schema = GENERIC_ACCOUNT_SCHEMA.extend(dict(add_to_accounts))
        accounts_validator = _make_account_validator(accounts_schema)
        add_to_config[
            vol.Optional(CONF_DEFAULT, default=lambda: accounts_schema({}))
        ] = accounts_validator
        add_to_config[vol.Optional(CONF_ACCOUNTS)] = vol.Any(
            vol.All(cv.ensure_list, [cv.string], lambda x: {y: accounts_schema({}) for y in x}),
            vol.Schema({cv.string: accounts_validator}),
        )

    return GENERIC_CONFIG_ENTRY_SCHEMA.extend(add_to_config)


PROFILE_TYPE_VALIDATOR = vol.In(API_TYPE_NAMES)


GENERIC_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        # Primary API configuration
        vol.Required(CONF_TYPE): PROFILE_TYPE_VALIDATOR,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEV_PRESENTATION, default=False): cv.boolean,
        # Additional API configuration
        vol.Optional(CONF_USER_AGENT): vol.All(
            cv.string, lambda x: " ".join(map(str.strip, x.split("\n")))
        ),
        vol.Optional(
            CONF_DEFAULT, default=lambda: GENERIC_ACCOUNT_SCHEMA({})
        ): GENERIC_ACCOUNT_VALIDATOR,
        vol.Optional(CONF_ACCOUNTS): vol.Any(
            vol.All(
                cv.ensure_list, [cv.string], lambda x: {y: GENERIC_ACCOUNT_SCHEMA({}) for y in x}
            ),
            vol.Schema({cv.string: GENERIC_ACCOUNT_VALIDATOR}),
        ),
    },
    extra=vol.PREVENT_EXTRA,
)

_CONFIG_VALIDATORS = [
    _make_provider_schema(
        provider_type="tomsk",
        add_to_accounts={
            vol.Optional("byt_only", default=False): cv.boolean,
        },
    ),
    GENERIC_CONFIG_ENTRY_SCHEMA,
]

CONFIG_ENTRY_SCHEMA = vol.All(
    vol.Schema(
        {
            # Set default type to 'moscow' before validating further
            vol.Optional(CONF_TYPE, default=API_TYPE_DEFAULT): PROFILE_TYPE_VALIDATOR,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    vol.Any(*_CONFIG_VALIDATORS),
)
