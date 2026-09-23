"""Константы интеграции «Яндекс меню»."""

DOMAIN = "yandex_menu"

# Соседние интеграции, на которые опираемся
YS_DOMAIN = "yandex_station"  # даёт авторизованную сессию к Квазару
YAHA_DOMAIN = "yandex_smart_home"  # отдаёт сущности HA в Алису

# Панель в боковом меню
PANEL_URL_PATH = "yandex-menu"
PANEL_STATIC_URL = "/yandex_menu_static"
PANEL_JS = "yandex-menu-panel.js"
PANEL_TITLE = "Яндекс меню"
PANEL_ICON = "mdi:account-voice"

# Настройка интеграции: показывать ли пункт в левом меню (по умолчанию да)
CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"

# Выбор, когда в HA несколько аккаунтов Яндекса или записей Yandex Smart Home (id записей)
CONF_YANDEX_ACCOUNT = "yandex_account"
CONF_YAHA_ENTRY = "yaha_entry"

API = "https://iot.quasar.yandex.ru"

# Потолок Яндекса: основное имя + 4 синонима
MAX_NAMES = 5

# Домены, которые Yandex Smart Home умеет отдавать в Алису (сверено с его device.py)
EXPOSABLE_DOMAINS = (
    "air_quality",
    "automation",
    "binary_sensor",
    "button",
    "camera",
    "climate",
    "cover",
    "event",
    "fan",
    "group",
    "humidifier",
    "input_boolean",
    "input_button",
    "input_text",
    "light",
    "lock",
    "media_player",
    "remote",
    "scene",
    "script",
    "sensor",
    "switch",
    "vacuum",
    "valve",
    "water_heater",
)

# У этих доменов всё решают показания: датчик с текстом вместо числа или без класса
# Яндекс не примет. Поэтому перед показом спрашиваем сам Yandex Smart Home.
CONDITIONAL_DOMAINS = (
    "air_quality",
    "binary_sensor",
    "camera",
    "event",
    "input_text",
    "sensor",
)

STORAGE_KEY = "yandex_menu.snapshots"
STORAGE_VERSION = 1
# Последний прочитанный список: панель показывает его сразу, пока Яндекс отвечает
SAVED_STORAGE_KEY = "yandex_menu.list"
# Настройки и карточки устройств: Яндекс отдаёт их по одному, в большом доме это минуты
CACHE_STORAGE_KEY = "yandex_menu.devices"

DATA_API = "api"
DATA_STORE = "store"
DATA_SNAPSHOTS = "snapshots"  # слепки текущего аккаунта
DATA_STORE_DATA = "store_data"  # всё хранилище: слепки по аккаунтам
DATA_DETAILS = "details"  # кэш карточек устройств
DATA_CONFIGS = "configs"  # кэш настроек устройств: имена, роль, сущность HA
DATA_CACHE_STORE = "cache_store"
DATA_CACHE_OWNER = "cache_owner"  # чей аккаунт в кэше настроек
DATA_STALE = "stale"  # сколько раз устройство меняли из панели: старые ответы не кэшируем
DATA_BUILD = "build"  # идущая сборка списка: новые запросы ждут её, а не запускают свою
DATA_BUILDS = "builds"  # все сборки очереди — при выгрузке останавливаем каждую
DATA_PROGRESS = "progress"  # как далеко зашла сборка — для панели
DATA_PROGRESS_LISTENERS = "progress_listeners"
DATA_CACHE = "cache"
DATA_SAVED = "saved"  # последний прочитанный список и когда он прочитан
DATA_SAVED_STORE = "saved_store"
DATA_SAVED_TURN = "saved_turn"  # номер сборки, чей список запомнен
DATA_WS_REGISTERED = "ws_registered"

CACHE_TTL = 15  # секунд, чтобы повторное открытие панели не дёргало Яндекс заново

VERSION = "0.2.3"
