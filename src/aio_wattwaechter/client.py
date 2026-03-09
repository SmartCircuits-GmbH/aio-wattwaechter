"""Async client for the WattWächter smart meter API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .exceptions import (
    WattwaechterAuthenticationError,
    WattwaechterBadRequestError,
    WattwaechterConnectionError,
    WattwaechterNotFoundError,
    WattwaechterPayloadTooLargeError,
    WattwaechterRateLimitError,
)
from .models import (
    AliveResponse,
    CaCertActionResponse,
    CaCertStatus,
    HighResHistory,
    LedInfo,
    LowResHistory,
    MeterData,
    OtaCheckResponse,
    SelfTestResult,
    Settings,
    SystemInfo,
    TimezoneEntry,
    TokenGenerateResponse,
    WifiScanResponse,
    _parse_alive,
    _parse_ca_cert_action,
    _parse_ca_cert_status,
    _parse_high_res_history,
    _parse_led_info,
    _parse_low_res_history,
    _parse_meter_data,
    _parse_ota_check,
    _parse_self_test,
    _parse_settings,
    _parse_system_info,
    _parse_timezones,
    _parse_token_generate,
    _parse_wifi_scan,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10


class Wattwaechter:
    """Async client for the WattWächter smart meter API.

    Authentication is disabled by default on the device. Pass a token
    only if authentication has been enabled.

    Args:
        host: Hostname or IP address of the device.
        token: Optional API token (READ or WRITE) for authentication.
        session: Optional aiohttp.ClientSession to reuse.
        request_timeout: Request timeout in seconds.

    Example:
        async with Wattwaechter("192.168.1.100") as client:
            data = await client.meter_data()
            print(f"Power: {data.power} W")
    """

    def __init__(
        self,
        host: str,
        *,
        token: str | None = None,
        session: aiohttp.ClientSession | None = None,
        request_timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        """Initialize the WattWächter client."""
        self._host = host
        self._token = token
        self._session = session
        self._close_session = False
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._base_url = f"http://{host}/api/v1"

    @property
    def host(self) -> str:
        """Return the device host."""
        return self._host

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an aiohttp session exists."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    def _headers(self, require_auth: bool = True) -> dict[str, str]:
        """Build request headers."""
        headers: dict[str, str] = {}
        if self._token and require_auth:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        require_auth: bool = True,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> aiohttp.ClientResponse:
        """Execute an HTTP request with automatic retry on 429/503.

        Returns the raw aiohttp response for further processing.
        """
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"
        last_err: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                async with asyncio.timeout(self._request_timeout):
                    resp = await session.request(
                        method,
                        url,
                        headers=self._headers(require_auth),
                        json=json_data,
                        params=params,
                    )
            except (asyncio.TimeoutError, aiohttp.ClientError) as err:
                raise WattwaechterConnectionError(
                    f"Cannot connect to {self._host}: {err}"
                ) from err

            if resp.status not in (429, 503):
                return resp

            # Retry on rate limit or device busy
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after else (attempt + 1)
            _LOGGER.debug(
                "Request to %s returned %s, retrying in %ss (attempt %d/%d)",
                path, resp.status, wait, attempt + 1, self._max_retries,
            )
            last_err = WattwaechterRateLimitError(
                "Rate limit exceeded", retry_after=wait
            ) if resp.status == 429 else WattwaechterConnectionError(
                f"Device busy (503), retry after {wait}s"
            )
            await asyncio.sleep(wait)

        raise last_err  # type: ignore[misc]

    def _handle_error_status(self, resp: aiohttp.ClientResponse, path: str) -> None:
        """Raise appropriate exceptions for HTTP error status codes."""
        if resp.status == 400:
            raise WattwaechterBadRequestError(
                f"Bad request to {path}"
            )

        if resp.status == 401:
            raise WattwaechterAuthenticationError("Invalid or missing API token")

        if resp.status == 403:
            raise WattwaechterAuthenticationError(
                "Forbidden — insufficient permissions"
            )

        if resp.status == 404:
            raise WattwaechterNotFoundError(
                f"Resource not found: {path}"
            )

        if resp.status == 413:
            raise WattwaechterPayloadTooLargeError(
                "Request payload too large"
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        require_auth: bool = True,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an API request and return the JSON response.

        Raises:
            WattwaechterConnectionError: On connection/timeout/unexpected errors.
            WattwaechterAuthenticationError: On 401/403 responses.
            WattwaechterBadRequestError: On 400 responses.
            WattwaechterNotFoundError: On 404 responses.
            WattwaechterPayloadTooLargeError: On 413 responses.
            WattwaechterRateLimitError: On 429 responses.
        """
        resp = await self._do_request(
            method, path, require_auth=require_auth,
            json_data=json_data, params=params,
        )

        if resp.status == 204:
            return {}

        self._handle_error_status(resp, path)

        if resp.status not in (200, 202):
            raise WattwaechterConnectionError(
                f"Unexpected status {resp.status} from {path}"
            )

        try:
            return await resp.json()
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise WattwaechterConnectionError(
                f"Invalid JSON response from {path}: {err}"
            ) from err

    async def _request_text(
        self,
        method: str,
        path: str,
        *,
        require_auth: bool = True,
        params: dict[str, str] | None = None,
    ) -> str | None:
        """Make an API request and return the text response.

        Returns None if no content is available (HTTP 204).
        """
        resp = await self._do_request(
            method, path, require_auth=require_auth, params=params,
        )

        if resp.status == 204:
            return None

        self._handle_error_status(resp, path)

        if resp.status not in (200, 202):
            raise WattwaechterConnectionError(
                f"Unexpected status {resp.status} from {path}"
            )

        return await resp.text()

    # --- System endpoints ---

    async def alive(self) -> AliveResponse:
        """Check device connectivity (no auth required).

        GET /api/v1/system/alive
        """
        data = await self._request("GET", "/system/alive", require_auth=False)
        return _parse_alive(data)

    async def system_info(self) -> SystemInfo:
        """Get system diagnostic information.

        GET /api/v1/system/info
        """
        data = await self._request("GET", "/system/info")
        return _parse_system_info(data)

    async def led(self) -> LedInfo:
        """Get current LED status.

        GET /api/v1/system/led
        """
        data = await self._request("GET", "/system/led")
        return _parse_led_info(data)

    async def selftest(self) -> SelfTestResult:
        """Run IR transceiver self-test (~2 seconds).

        POST /api/v1/system/selftest
        """
        data = await self._request("POST", "/system/selftest")
        return _parse_self_test(data)

    async def wifi_scan(self, *, refresh: bool = False) -> WifiScanResponse:
        """Scan for available WiFi networks.

        GET /api/v1/system/wifi_scan
        """
        params = {"refresh": "true"} if refresh else None
        data = await self._request(
            "GET", "/system/wifi_scan", require_auth=False, params=params
        )
        return _parse_wifi_scan(data)

    async def timezones(self) -> list[TimezoneEntry]:
        """Get all supported timezones.

        GET /api/v1/system/timezones
        Returns list of TimezoneEntry with name, gmt_offset, daylight_offset.
        """
        resp = await self._do_request("GET", "/system/timezones")
        self._handle_error_status(resp, "/system/timezones")
        try:
            data = await resp.json()
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise WattwaechterConnectionError(
                f"Invalid JSON response from /system/timezones: {err}"
            ) from err
        return _parse_timezones(data)

    async def reboot(self) -> bool:
        """Reboot the device (requires WRITE token).

        POST /api/v1/system/reboot
        """
        data = await self._request("POST", "/system/reboot")
        return data.get("rebooting", False)

    # --- History / Meter endpoints ---

    async def meter_data(self) -> MeterData | None:
        """Get the latest smart meter reading.

        GET /api/v1/history/latest
        Returns None if no data is available yet (HTTP 204).
        """
        data = await self._request("GET", "/history/latest")
        if not data:
            return None
        return _parse_meter_data(data)

    async def history_high_res(self, date: str) -> HighResHistory:
        """Get 15-minute resolution history for a specific date.

        GET /api/v1/history/highRes?date=YYYY-MM-DD

        Args:
            date: Date in YYYY-MM-DD format.
        """
        data = await self._request(
            "GET", "/history/highRes", params={"date": date}
        )
        return _parse_high_res_history(data)

    async def history_low_res(self, start: str, days: int) -> LowResHistory:
        """Get daily resolution history over a date range.

        GET /api/v1/history/lowRes?start=YYYY-MM-DD&days=N

        Args:
            start: Start date in YYYY-MM-DD format.
            days: Number of days (1-31).
        """
        data = await self._request(
            "GET", "/history/lowRes",
            params={"start": start, "days": str(days)},
        )
        return _parse_low_res_history(data)

    # --- Log endpoints ---

    async def logs_rawdump(self) -> bytes | None:
        """Get raw smart meter buffer dump (binary SML data).

        GET /api/v1/logs/rawdump
        Returns None if no data is available (HTTP 204).
        """
        resp = await self._do_request("GET", "/logs/rawdump")
        if resp.status == 204:
            return None
        self._handle_error_status(resp, "/logs/rawdump")
        if resp.status not in (200, 202):
            raise WattwaechterConnectionError(
                f"Unexpected status {resp.status} from /logs/rawdump"
            )
        return await resp.read()

    async def logs_persistent(self) -> str:
        """Get persistent CSV log file from device storage.

        GET /api/v1/logs/persistent
        """
        result = await self._request_text("GET", "/logs/persistent")
        return result or ""

    async def logs_ram(self) -> str:
        """Get current RAM log snapshot.

        GET /api/v1/logs/ram
        """
        result = await self._request_text("GET", "/logs/ram")
        return result or ""

    # --- OTA endpoints ---

    async def ota_check(self) -> OtaCheckResponse:
        """Check for firmware updates.

        GET /api/v1/ota/check
        """
        data = await self._request("GET", "/ota/check")
        return _parse_ota_check(data)

    async def ota_start(self) -> bool:
        """Start the OTA firmware update (requires WRITE token).

        POST /api/v1/ota/start
        The device will download, install, and reboot.
        """
        data = await self._request("POST", "/ota/start")
        return data.get("ok", False)

    # --- Settings endpoints ---

    async def settings(self) -> Settings:
        """Get all device settings.

        GET /api/v1/settings
        Note: Passwords are excluded from the response.
        """
        data = await self._request("GET", "/settings")
        return _parse_settings(data)

    async def update_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Update device settings (requires WRITE token).

        POST /api/v1/settings
        Partial update — only send fields you want to change.

        Args:
            settings: Dictionary of settings to update.

        Returns:
            The applied settings as echoed by the device.
        """
        data = await self._request("POST", "/settings", json_data=settings)
        return data.get("applied", {})

    # --- Auth endpoints ---

    async def generate_tokens(self) -> TokenGenerateResponse:
        """Generate new API tokens (requires WRITE token).

        POST /api/v1/auth/tokens/generate
        Tokens are pending until confirmed within 60 seconds.
        """
        data = await self._request("POST", "/auth/tokens/generate")
        return _parse_token_generate(data)

    async def confirm_tokens(self, new_write_token: str) -> bool:
        """Confirm and activate pending tokens (requires WRITE token).

        POST /api/v1/auth/tokens/confirm

        Args:
            new_write_token: The new WRITE token received from generate_tokens().
        """
        data = await self._request(
            "POST",
            "/auth/tokens/confirm",
            json_data={"new_write_token": new_write_token},
        )
        return data.get("success", False)

    async def setup_token(self) -> dict[str, str]:
        """Get initial setup tokens (only before first WiFi connection).

        GET /api/v1/setup/token
        Returns dict with 'readToken' and 'writeToken'.
        Raises WattwaechterAuthenticationError (403) if initial setup is complete.
        """
        return await self._request(
            "GET", "/setup/token", require_auth=False
        )

    # --- MQTT CA endpoints ---

    async def mqtt_ca_status(self) -> CaCertStatus:
        """Get custom CA certificate status.

        GET /api/v1/mqtt/ca
        """
        data = await self._request("GET", "/mqtt/ca")
        return _parse_ca_cert_status(data)

    async def mqtt_ca_upload(self, certificate: str) -> CaCertActionResponse:
        """Upload a custom CA certificate for MQTT TLS (requires WRITE token).

        POST /api/v1/mqtt/ca

        Args:
            certificate: PEM-encoded certificate string.
        """
        data = await self._request(
            "POST", "/mqtt/ca", json_data={"certificate": certificate}
        )
        return _parse_ca_cert_action(data)

    async def mqtt_ca_delete(self) -> CaCertActionResponse:
        """Delete the custom CA certificate (requires WRITE token).

        DELETE /api/v1/mqtt/ca
        Raises WattwaechterNotFoundError if no custom certificate exists.
        """
        data = await self._request("DELETE", "/mqtt/ca")
        return _parse_ca_cert_action(data)

    # --- Cloud pairing endpoints ---

    async def cloud_pair(self, pairing_token: str) -> bool:
        """Submit a cloud pairing token (requires WRITE token).

        POST /api/v1/cloud/pair

        Args:
            pairing_token: Pairing token in format WW-XXXXXXXX.
        """
        data = await self._request(
            "POST", "/cloud/pair", json_data={"pairing_token": pairing_token}
        )
        return data.get("success", False)

    async def cloud_unpair(self) -> bool:
        """Remove cloud pairing (requires WRITE token).

        DELETE /api/v1/cloud/pair
        """
        data = await self._request("DELETE", "/cloud/pair")
        return data.get("success", False)

    # --- Context manager ---

    async def __aenter__(self) -> Wattwaechter:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context and close session if we own it."""
        await self.close()

    async def close(self) -> None:
        """Close the session if we created it."""
        if self._close_session and self._session and not self._session.closed:
            await self._session.close()
