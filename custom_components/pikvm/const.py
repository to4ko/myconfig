"""Constants for the PiKVM integration."""

from typing import Final

DOMAIN: Final = "pikvm"
MANUFACTURER: Final = "PiKVM"

# Configuration keys
CONF_HOST: Final = "host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_TOTP: Final = "totp"
CONF_CERTIFICATE: Final = "certificate"
CONF_SERIAL: Final = "serial"
CONF_MODEL: Final = "model"

# Default values
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = "admin"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 300
