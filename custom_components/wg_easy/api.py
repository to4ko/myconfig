from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)


class WGEasyApiError(Exception):
    """Raised when the WG Easy API cannot be reached or returns an error."""


class WGEasyAuthError(WGEasyApiError):
    """Raised when authentication with the WG Easy API fails."""


class WGEasyNotDetectedError(WGEasyApiError):
    """Raised when a server responds, but doesn't look like wg-easy at all.

    Distinct from a plain WGEasyApiError (network/connectivity failure) so
    the config flow can show a more specific, human message: the address
    was reachable, it just isn't a wg-easy install.
    """


class WGEasyV15Client:
    """Talks to wg-easy v15's Bearer-token-secured metrics endpoint.

    v15 has no general Bearer-token JSON API - the only endpoint secured by
    a Bearer token is the metrics feature (Admin Panel -> General ->
    Metrics), and its JSON variant at "{base_url}/metrics/json" returns
    exactly the {clients: [...], wireguard_configured_peers, ...} shape
    this integration expects (confirmed against wg-easy's own
    src/server/routes/metrics/json.get.ts). The general "/api/..." REST
    API is Basic Auth only and unrelated to this token.

    The configured URL is treated as the server's base address (optionally
    including a reverse-proxy subpath, e.g. "https://host/wireguard") and
    "/metrics/json" is appended automatically unless it's already there,
    so entering just the base address is enough.
    """

    def __init__(
        self,
        session: ClientSession,
        url: str,
        token: str | None,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._url = self._normalize_url(url)
        self._token = token
        self._verify_ssl = verify_ssl

    @staticmethod
    def _normalize_url(url: str) -> str:
        base = (url or "").rstrip("/")
        if base.endswith("/metrics/json"):
            return base
        return f"{base}/metrics/json"

    async def async_fetch_raw(self) -> bytes:
        if not self._token:
            raise WGEasyApiError("No API token configured for the v15 API")

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        try:
            async with self._session.get(
                self._url, headers=headers, ssl=self._verify_ssl
            ) as response:
                if response.status == 401:
                    raise WGEasyAuthError("Unauthorized - check API token")
                if response.status >= 400:
                    body = await response.text()
                    raise WGEasyApiError(f"HTTP {response.status}: {body[:200]}")
                return await response.read()
        except ClientError as err:
            raise WGEasyApiError(f"Request failed: {err}") from err


class WGEasyV14Client:
    """Talks to a wg-easy v14 style API: password login -> session cookie -> REST endpoint."""

    def __init__(
        self,
        session: ClientSession,
        url: str,
        password: str | None,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._base_url = url.rstrip("/")
        self._password = password
        self._verify_ssl = verify_ssl
        self._session_cookie: str | None = None
        self._no_password_required = False

    async def _async_login(self) -> None:
        if not self._password:
            # Some wg-easy v14 deployments run with no PASSWORD_HASH set at
            # all (auth disabled server-side). Their login endpoint still
            # rejects every password attempt with 401, but the data
            # endpoints work with no session/cookie at all. Check
            # GET /api/session's requiresPassword flag before giving up.
            session_url = f"{self._base_url}/api/session"
            try:
                async with self._session.get(
                    session_url, ssl=self._verify_ssl
                ) as response:
                    if response.status == 200:
                        try:
                            data = await response.json(content_type=None)
                        except ValueError:
                            data = None
                        if isinstance(data, dict) and data.get("requiresPassword") is False:
                            self._no_password_required = True
                            return
            except ClientError as err:
                raise WGEasyApiError(
                    f"Could not check session requirements: {err}"
                ) from err
            raise WGEasyApiError("No password configured for the v14 API")

        session_url = f"{self._base_url}/api/session"
        try:
            async with self._session.post(
                session_url, json={"password": self._password}, ssl=self._verify_ssl
            ) as response:
                if response.status == 401:
                    raise WGEasyAuthError("Unauthorized - check password")
                if response.status >= 400:
                    body = await response.text()
                    raise WGEasyApiError(f"Login HTTP {response.status}: {body[:200]}")

                try:
                    login_data = await response.json()
                except ValueError as err:
                    raise WGEasyApiError(f"Invalid login response: {err}") from err

                if isinstance(login_data, dict) and login_data.get("success") is False:
                    raise WGEasyAuthError("wg-easy rejected the configured password")

                cookie = response.cookies.get("connect.sid")
                if not cookie:
                    raise WGEasyApiError("Login succeeded but no session cookie was returned")
                self._session_cookie = cookie.value
        except ClientError as err:
            raise WGEasyApiError(f"Login request failed: {err}") from err

    async def async_fetch_raw(self) -> bytes:
        if not self._session_cookie and not self._no_password_required:
            await self._async_login()

        data_url = f"{self._base_url}/api/wireguard/client"
        cookies = {"connect.sid": self._session_cookie} if self._session_cookie else {}

        try:
            async with self._session.get(
                data_url,
                headers={"Accept": "application/json"},
                cookies=cookies,
                ssl=self._verify_ssl,
            ) as response:
                if response.status == 401:
                    # Session likely expired; drop it so the next poll logs in again.
                    self._session_cookie = None
                    raise WGEasyAuthError("Session expired - will re-authenticate next poll")
                if response.status >= 400:
                    body = await response.text()
                    raise WGEasyApiError(f"HTTP {response.status}: {body[:200]}")
                return await response.read()
        except ClientError as err:
            raise WGEasyApiError(f"Request failed: {err}") from err


async def _looks_like_json(response) -> bool:
    """True if a response is actually JSON, by header or by successfully parsing it.

    Used to avoid being fooled by servers that return HTTP 200/401/etc. for
    every path (e.g. an unrelated single-page app with catch-all client-side
    routing serving its index.html for any URL) instead of a real API
    response.
    """
    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type.lower():
        return True
    try:
        await response.json(content_type=None)
    except ValueError:
        return False
    return True


async def async_probe_wg_easy_version(
    session: ClientSession, url: str, verify_ssl: bool = True
) -> str:
    """Unauthenticated probe to tell wg-easy v14 apart from v15, before any credentials.

    Looks for a version-specific *positive* signature for each, rather than
    assuming "not v14 => v15" - pointing this at an unrelated web service
    that happens to respond to every path (a common pattern for single-page
    apps) would otherwise be misclassified as v15 instead of failing.

    - v14 signature: unauthenticated ``GET {base_url}/api/release`` returns
      the running release as a bare JSON string (confirmed against v14's
      src/lib/Server.js - registered before the password-check middleware).
    - v15 signature: ``GET {base_url}/metrics/json`` is a real route that
      exists only on v15 (its metrics feature). Even without a token it
      should answer with 200 (no metrics password configured) or
      401/403 (password required) and an actual JSON body - never a plain
      404, and never an HTML page.

    If neither signature matches, a WGEasyNotDetectedError is raised so the
    caller can tell the user this doesn't look like a wg-easy server,
    instead of silently guessing. A genuine connection failure (bad URL,
    DNS, refused, timeout, TLS error) raises the plain WGEasyApiError
    instead, so the two cases can get distinct, more useful error messages.

    Deliberately does NOT use Home Assistant's shared client session
    (``session`` is accepted for API-compatibility with callers but
    unused). wg-easy's web UI sets cookies (theme, i18n_redirected, ...)
    on every response, and HA's shared session is process-wide - if
    another wg_easy config entry is already polling this same host with a
    valid Bearer token, its cookies end up in that shared jar too. Using
    a throwaway session with an empty cookie jar makes this probe behave
    like a fresh client every time, regardless of what else is talking to
    the same host.

    The ``/metrics/json`` request also sends a deliberately-bogus
    ``Authorization: Bearer`` header (plus ``Accept: application/json``).
    Even with a clean cookie jar, a request with *no* Authorization header
    at all can still get routed through wg-easy's browser/session-login
    logic on some deployments (reverse proxies and the app's own auth
    middleware may treat "no credentials presented" as "anonymous browser
    visit -> redirect to /login" rather than "API client -> 401 JSON").
    Presenting *a* Bearer token - even an invalid one - unambiguously
    signals "this is an API-style request" to the same auth middleware
    real token-authenticated requests go through (see
    ``WGEasyV15Client.async_fetch_raw``, which reliably gets a clean JSON
    response this way), so the server evaluates and rejects it as bad
    credentials (401/403 JSON) instead of redirecting.
    """
    # Imported locally to avoid a circular import with const.py's importers.
    from .const import API_VERSION_V14, API_VERSION_V15

    base_url = (url or "").rstrip("/")

    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as probe_session:
        try:
            async with probe_session.get(
                f"{base_url}/api/release", ssl=verify_ssl
            ) as response:
                if response.status == 200:
                    try:
                        body = await response.json(content_type=None)
                    except ValueError:
                        body = None
                    if isinstance(body, (str, int, float)) and str(body).strip():
                        return API_VERSION_V14

            async with probe_session.get(
                f"{base_url}/metrics/json",
                headers={
                    "Authorization": "Bearer wg-easy-ha-integration-version-probe",
                    "Accept": "application/json",
                },
                ssl=verify_ssl,
            ) as response:
                looks_json = await _looks_like_json(response)
                _LOGGER.debug(
                    "wg-easy probe: GET %s -> final_url=%s status=%s "
                    "content-type=%r looks_like_json=%s",
                    f"{base_url}/metrics/json",
                    response.url,
                    response.status,
                    response.headers.get("Content-Type"),
                    looks_json,
                )
                if response.status in (200, 401, 403) and looks_json:
                    return API_VERSION_V15
        except ClientError as err:
            raise WGEasyApiError(f"Could not reach {base_url}: {err}") from err

    raise WGEasyNotDetectedError(
        f"{base_url} does not look like a wg-easy server (neither the v14 "
        "nor the v15 signature endpoint responded as expected). Check the "
        "address, or pick the API version manually if you're sure it's "
        "correct."
    )
