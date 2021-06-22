"""Constants for lkcomu_interrao integration"""
from typing import Final

DOMAIN: Final = "lkcomu_interrao"

ATTRIBUTION_EN: Final = "Data acquired from %s"
ATTRIBUTION_RU: Final = "Данные получены с %s"

ATTR_ACCOUNT_CODE: Final = "account_code"
ATTR_ACCOUNT_ID: Final = "account_id"
ATTR_ADDRESS: Final = "address"
ATTR_AGENT: Final = "agent"
ATTR_AMOUNT: Final = "amount"
ATTR_BENEFITS: Final = "benefits"
ATTR_CALL_PARAMS: Final = "call_params"
ATTR_CHARGED: Final = "charged"
ATTR_CLEAR: Final = "clear"
ATTR_COMMENT: Final = "comment"
ATTR_CORRECT: Final = "correct"
ATTR_COST: Final = "cost"
ATTR_DESCRIPTION: Final = "description"
ATTR_DETAILS: Final = "details"
ATTR_END: Final = "end"
ATTR_FULL_NAME: Final = "full_name"
ATTR_GROUP: Final = "group"
ATTR_IGNORE_INDICATIONS: Final = "ignore_indications"
ATTR_IGNORE_PERIOD: Final = "ignore_period"
ATTR_INCREMENTAL: Final = "incremental"
ATTR_INDICATIONS: Final = "indications"
ATTR_INITIAL: Final = "initial"
ATTR_INSTALL_DATE: Final = "install_date"
ATTR_INSURANCE: Final = "insurance"
ATTR_INVOICE_ID: Final = "invoice_id"
ATTR_LAST_INDICATIONS_DATE: Final = "last_indications_date"
ATTR_LAST_PAYMENT_AMOUNT: Final = "last_payment_amount"
ATTR_LAST_PAYMENT_DATE: Final = "last_payment_date"
ATTR_LAST_PAYMENT_STATUS: Final = "last_payment_status"
ATTR_LIVING_AREA: Final = "living_area"
ATTR_METER_CATEGORY: Final = "meter_category"
ATTR_METER_CODE: Final = "meter_code"
ATTR_METER_MODEL: Final = "meter_model"
ATTR_MODEL: Final = "model"
ATTR_NOTIFICATION: Final = "notification"
ATTR_PAID: Final = "paid"
ATTR_PAID_AT: Final = "paid_at"
ATTR_PENALTY: Final = "penalty"
ATTR_PERIOD: Final = "period"
ATTR_PREVIOUS: Final = "previous"
ATTR_PROVIDER_NAME: Final = "provider_name"
ATTR_PROVIDER_TYPE: Final = "provider_type"
ATTR_REASON: Final = "reason"
ATTR_RECALCULATIONS: Final = "recalculations"
ATTR_REMAINING_DAYS: Final = "remaining_days"
ATTR_RESULT: Final = "result"
ATTR_SERVICE_NAME: Final = "service_name"
ATTR_SERVICE_TYPE: Final = "service_type"
ATTR_START: Final = "start"
ATTR_STATUS: Final = "status"
ATTR_SUBMIT_PERIOD_ACTIVE: Final = "submit_period_active"
ATTR_SUBMIT_PERIOD_END: Final = "submit_period_end"
ATTR_SUBMIT_PERIOD_START: Final = "submit_period_start"
ATTR_SUCCESS: Final = "success"
ATTR_SUM: Final = "sum"
ATTR_TOTAL: Final = "total"
ATTR_TOTAL_AREA: Final = "total_area"
ATTR_UNIT: Final = "unit"

CONF_ACCOUNTS: Final = "accounts"
CONF_DEV_PRESENTATION: Final = "dev_presentation"
CONF_LAST_INVOICE: Final = "last_invoice"
CONF_LAST_PAYMENT: Final = "last_payment"
CONF_LOGOS: Final = "logos"
CONF_METERS: Final = "meters"
CONF_NAME_FORMAT: Final = "name_format"
CONF_USER_AGENT: Final = "user_agent"

DATA_API_OBJECTS: Final = DOMAIN + "_api_objects"
DATA_ENTITIES: Final = DOMAIN + "_entities"
DATA_FINAL_CONFIG: Final = DOMAIN + "_final_config"
DATA_PROVIDER_LOGOS: Final = DOMAIN + "_provider_logos"
DATA_UPDATE_DELEGATORS: Final = DOMAIN + "_update_delegators"
DATA_UPDATE_LISTENERS: Final = DOMAIN + "_update_listeners"
DATA_YAML_CONFIG: Final = DOMAIN + "_yaml_config"

DEFAULT_NAME_FORMAT_EN_ACCOUNTS: Final = "{provider_code_upper} {account_code} {type_en_cap}"
DEFAULT_NAME_FORMAT_EN_METERS: Final = "{provider_code_upper} {account_code} {type_en_cap} {code}"
DEFAULT_NAME_FORMAT_EN_LAST_INVOICE: Final = "{provider_code_upper} {account_code} {type_en_cap}"
DEFAULT_NAME_FORMAT_EN_LAST_PAYMENT: Final = "{provider_code_upper} {account_code} {type_en_cap}"

DEFAULT_NAME_FORMAT_RU_ACCOUNTS: Final = "{provider_code_upper} {account_code} {type_ru_cap}"
DEFAULT_NAME_FORMAT_RU_METERS: Final = "{provider_code_upper} {account_code} {type_ru_cap} {code}"
DEFAULT_NAME_FORMAT_RU_LAST_INVOICE: Final = "{provider_code_upper} {account_code} {type_ru_cap}"
DEFAULT_NAME_FORMAT_RU_LAST_PAYMENT: Final = "{provider_code_upper} {account_code} {type_ru_cap}"

DEFAULT_MAX_INDICATIONS: Final = 3
DEFAULT_SCAN_INTERVAL: Final = 60 * 60  # 1 hour

API_TYPE_DEFAULT: Final = "moscow"
API_TYPE_NAMES: Final = {
    "altai": "ЛК Алтай (АО «АлтайЭнергосбыт»)",
    "bashkortostan": "ЛКК ЭСКБ (Башэлектросбыт)",
    "moscow": "ЕЛК ЖКХ (АО «Мосэнергосбыт», МосОблЕИРЦ, ПАО «Россети Московский регион»)",
    "oryol": "ЛКК Орел (ООО «Орловский энергосбыт»)",
    "saratov": "ЛК Саратов (ПАО «Саратовэнерго»)",
    "sevesk": "ЕЛК Вологда (Северная сбытовая компания)",
    "tambov": "ЛК ТЭСК (Тамбовская энергосбытовая компания)",
    "tomsk": "ЕЛК Томск (Томскэнергосбыт / Томск РТС)",
    "volga": "ЛКК ЭСВ (Энергосбыт Волга)",
}


SUPPORTED_PLATFORMS: Final = ("sensor", "binary_sensor")

FORMAT_VAR_ACCOUNT_CODE: Final = "account_code"
FORMAT_VAR_ACCOUNT_ID: Final = "account_id"
FORMAT_VAR_CODE: Final = "code"
FORMAT_VAR_ID: Final = "id"
FORMAT_VAR_PROVIDER_CODE: Final = "provider_code"
FORMAT_VAR_PROVIDER_NAME: Final = "provider_name"
FORMAT_VAR_TYPE_EN: Final = "type_en"
FORMAT_VAR_TYPE_RU: Final = "type_ru"
