"""Handle certificate-related operations for PiKVM integration.
The PiKVM uses non-standard certificates, so we need to handle them manually.
Some of the expected certificatet types are:
- Non-TLSV3 compliant self-signed certificates by default.
- TLSV3 self-signed certificates
- TLSV3 certificates signed by self-signed CA
- TLSV3 certificates signed by a CA
The workarounds found in this cert_handler.py are intended to allow operation
under all circumstances assuming the PiKVM was correctly configured and not 
currently being intercepted.  The PiKVM public certificate will be recorded
during the time of the initial setup and stored in the Home Assistant configuration.
When loaded, the certificate will be used to establish a secure connection to the PiKVM.
Due to this, we are able to bypass the certificate verification process and establish
a secure connection to the PiKVM.

This module provides functions to fetch and serialize the certificate from the device. 
It also provides a function to check if the device is a PiKVM and return its serial number.
"""

from collections import namedtuple
import functools
import logging
import os
import socket
import ssl
import tempfile
import warnings

import OpenSSL
import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_MODEL, CONF_NAME, CONF_SERIAL

warnings.simplefilter("ignore", InsecureRequestWarning)

_LOGGER = logging.getLogger(__name__)


class SSLContextAdapter(HTTPAdapter):
    """An HTTP adapter that uses a custom SSL context."""

    def __init__(self, ssl_context, *args, **kwargs) -> None:
        """Initialize the adapter with the custom SSL context. This method is called by the session."""
        self.ssl_context = ssl_context
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs) -> None:
        """Initialize the pool manager with the custom SSL context. This method is called by the session."""
        kwargs["ssl_context"] = self.ssl_context
        super().init_poolmanager(*args, **kwargs)

    def cert_verify(self, conn, *args, **kwargs) -> None:
        """Disable certificate verification. This method is called by the pool manager."""
        conn.assert_hostname = False
        conn.cert_reqs = ssl.CERT_NONE


async def create_session_with_cert(hass: HomeAssistant | None, serialized_cert=None):
    cert_file_path = None
    try:
        session = requests.Session()

        # Create an SSL context that disables all verifications
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False  # Disable hostname verification
        context.verify_mode = ssl.CERT_NONE  # Disable certificate verification

        if serialized_cert:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file:
                cert_file.write(serialized_cert.encode("utf-8"))
                cert_file_path = cert_file.name
            if hass is not None:
                await hass.async_add_executor_job(
                    context.load_verify_locations, cert_file_path
                )
            else:
                context.load_verify_locations(cert_file_path)

        adapter = SSLContextAdapter(context)
        session.mount("https://", adapter)

        _LOGGER.debug("Created session with custom SSL context using the certificate")
        return session, cert_file_path if serialized_cert else None
    except Exception as e:
        _LOGGER.error("Error creating session with certificate: %s", e)
        return None, None


async def fetch_serialized_cert(hass: HomeAssistant, url: str) -> str:
    """Fetch and serialize the certificate."""
    return await hass.async_add_executor_job(_fetch_and_serialize_cert, url)


def _fetch_and_serialize_cert(url):
    """Fetch the certificate from the given URL and serializes it.

    Args:
        url (str): The URL from which to fetch the certificate.

    Returns:
        str: The serialized certificate in PEM format, or None if an error occurred.

    Raises:
        Exception: If there was an error fetching or serializing the certificate.

    """
    try:
        hostname = url.replace("https://", "").replace("http://", "").split("/")[0]
        port = 443

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        conn = context.wrap_socket(
            socket.socket(socket.AF_INET), server_hostname=hostname
        )
        conn.connect((hostname, port))

        # Get the certificate
        cert = conn.getpeercert(True)
        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert)

        # Serialize the certificate
        serialized_cert = OpenSSL.crypto.dump_certificate(
            OpenSSL.crypto.FILETYPE_PEM, x509
        ).decode("utf-8")
        conn.close()
        return serialized_cert  # noqa: TRY300

    except (OSError, ssl.SSLError, OpenSSL.crypto.Error) as e:
        _LOGGER.error("Error fetching or serializing certificate from %s: %s", url, e)
        if "conn" in locals() and conn:
            conn.close()
        return None


def format_url(input_url):
    """Ensure the URL is properly formatted."""
    if not input_url.startswith("http"):
        input_url = f"https://{input_url}"
    return input_url.rstrip("/")


PiKVMResponse = namedtuple(
    "PiKVMResponse", ["success", "model", "serial", "name", "error"]
)


async def is_pikvm_device(
    hass: HomeAssistant | None, url: str, username: str, password: str, cert: str
) -> tuple:
    """Check if the device is a PiKVM and return its serial number.

    Args:
      hass: HomeAssistant instance.
      url: The URL of the device.
      username: The username for the device.
      password: The password for the device.
      cert: The certificate for the device.

    Returns:
    - A tuple containing the success status, model, serial number, name, and error
    code if an error occurred. The error code may contain an HTTP status code.

    """
    url = format_url(url)
    _LOGGER.debug("Checking PiKVM device at %s with username %s", url, username)

    try:
        if hass is not None:
            session, cert_file_path = await create_session_with_cert(hass, cert)
        else:
            session, cert_file_path = await create_session_with_cert(None, cert)
        if not session:
            _LOGGER.error("Failed to create session")
            return PiKVMResponse(False, None, None, None, "HomeAssistantNoneError")

        if hass is not None:
            response = await hass.async_add_executor_job(
                functools.partial(
                    session.get,
                    f"{url}/api/info",
                    auth=HTTPBasicAuth(username, password),
                )
            )
        else:
            response = session.get(
                f"{url}/api/info", auth=HTTPBasicAuth(username, password)
            )

        _LOGGER.debug("Received response status code: %s", response.status_code)
        response.raise_for_status()

        data = response.json()
        _LOGGER.debug("Parsed response JSON: %s", data)

        if data.get("ok", False):
            result = data.get("result", {})
            hw = result.get("hw", {})
            platform = hw.get("platform", {})
            meta = result.get("meta", {})
            server = meta.get("server", {})

            serial = platform.get(CONF_SERIAL, None).lower()
            model = platform.get(CONF_MODEL, None)
            name = server.get(CONF_NAME, None)

            _LOGGER.debug("Extracted serial number: %s", serial)
            return PiKVMResponse(True, model, serial, name, None)

        _LOGGER.error("Device check failed: 'ok' key not present or false")
        return PiKVMResponse(False, None, None, None, "GenericException")

    except requests.exceptions.HTTPError as err:
        _LOGGER.warn("HTTPError checking PiKVM device at %s: %s", url, err)
        status_code = err.response.status_code
        if status_code in [401, 403]:
            return PiKVMResponse(False, None, None, None, "Exception_HTTP403")
        if status_code == 502:
            return PiKVMResponse(False, None, None, None, "Exception_HTTP502")
        # Generic HTTP error
        _LOGGER.warn("Unhandled HTTP status code: %s", status_code)
        return PiKVMResponse(False, None, None, None, "unhandled_http_error")
    except requests.exceptions.ConnectionError as err:
        _LOGGER.warn("ConnectionError checking PiKVM device at %s: %s", url, err)
        return PiKVMResponse(False, None, None, None, "cannot_connect")
    except requests.exceptions.Timeout as err:
        _LOGGER.warn("Timeout checking PiKVM device at %s: %s", url, err)
        return PiKVMResponse(False, None, None, None, "timeout")
    except requests.exceptions.RequestException as err:
        _LOGGER.warn("RequestException checking PiKVM device at %s: %s", url, err)
        return PiKVMResponse(False, None, None, None, "unknown_request_exception")

    except ValueError as err:
        _LOGGER.warn("ValueError while parsing response JSON from %s: %s", url, err)
        return PiKVMResponse(False, None, None, None, "Exception_JSON")

    finally:
        if cert_file_path and os.path.exists(cert_file_path):
            try:
                os.remove(cert_file_path)
                _LOGGER.debug("Temporary certificate file removed: %s", cert_file_path)
            except OSError as e:
                _LOGGER.warning("Failed to remove temporary certificate file: %s", e)
