DOMAIN = "wg_easy"
DEFAULT_POLL_INTERVAL = 30
DEFAULT_ONLINE_TIMEOUT_MINUTES = 5  # legacy, kept only for one-time migration
DEFAULT_ONLINE_TIMEOUT_SECONDS = 300
CONF_ONLINE_TIMEOUT_MINUTES = "online_timeout_minutes"  # legacy option key
CONF_ONLINE_TIMEOUT_SECONDS = "online_timeout_seconds"

CONF_API_VERSION = "api_version"
CONF_RESOLVED_API_VERSION = "resolved_api_version"
API_VERSION_AUTO = "auto"
API_VERSION_V14 = "v14"
API_VERSION_V15 = "v15"
API_VERSIONS = [API_VERSION_AUTO, API_VERSION_V14, API_VERSION_V15]

CONF_VERIFY_SSL = "verify_ssl"
DEFAULT_VERIFY_SSL = True

PLATFORMS = ["sensor", "binary_sensor"]
SERVER_DEVICE_ID = "wireguard_server"
ENTITY_ID_PREFIX = "wg"
