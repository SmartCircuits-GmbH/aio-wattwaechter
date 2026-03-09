"""Tests for the Wattwaechter client."""

from __future__ import annotations

import pytest
import aiohttp
from aioresponses import aioresponses

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterBadRequestError,
    WattwaechterConnectionError,
    WattwaechterNotFoundError,
    WattwaechterPayloadTooLargeError,
    WattwaechterRateLimitError,
)
from aio_wattwaechter.models import (
    LedColor,
    LedMode,
    LedStatus,
)

from .conftest import BASE_URL


# --- System endpoints ---


async def test_alive(mock_api: aioresponses) -> None:
    """Test alive endpoint."""
    mock_api.get(
        f"{BASE_URL}/system/alive",
        payload={"alive": True, "version": "1.0.3"},
    )
    async with Wattwaechter("192.168.1.100") as client:
        result = await client.alive()
    assert result.alive is True
    assert result.version == "1.0.3"


async def test_system_info(mock_api: aioresponses) -> None:
    """Test system info endpoint."""
    mock_api.get(
        f"{BASE_URL}/system/info",
        payload={
            "uptime": [{"name": "Uptime", "value": "5h 30m", "unit": ""}],
            "wifi": [{"name": "RSSI", "value": "-45", "unit": "dBm"}],
            "ap": [],
            "esp": [{"name": "Chip", "value": "ESP32-S3", "unit": ""}],
            "heap": [{"name": "Free", "value": "150000", "unit": "bytes"}],
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.system_info()
    assert len(result.uptime) == 1
    assert result.uptime[0].name == "Uptime"
    assert result.get_value("wifi", "RSSI") == "-45"
    assert result.get_value("wifi", "nonexistent") is None


async def test_led(mock_api: aioresponses) -> None:
    """Test LED endpoint."""
    mock_api.get(
        f"{BASE_URL}/system/led",
        payload={
            "status": "OK",
            "priority": 1,
            "color": "green",
            "mode": "dimmed",
            "rgb": {"r": 0, "g": 255, "b": 0},
            "enabled": True,
            "active_statuses": {"ok": True, "error": False},
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.led()
    assert result.status == LedStatus.OK
    assert result.color == LedColor.GREEN
    assert result.mode == LedMode.DIMMED
    assert result.rgb.g == 255
    assert result.enabled is True


async def test_selftest(mock_api: aioresponses) -> None:
    """Test self-test endpoint."""
    mock_api.post(
        f"{BASE_URL}/system/selftest",
        payload={"success": True, "result": "SUCCESS", "message": "IR-Transceiver OK"},
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.selftest()
    assert result.success is True
    assert result.result == "SUCCESS"


async def test_wifi_scan(mock_api: aioresponses) -> None:
    """Test WiFi scan endpoint."""
    mock_api.get(
        f"{BASE_URL}/system/wifi_scan",
        payload={
            "networks": [
                {"ssid": "MyNetwork", "rssi": -45},
                {"ssid": "Other", "rssi": -67},
            ],
            "count": 2,
        },
    )
    async with Wattwaechter("192.168.1.100") as client:
        result = await client.wifi_scan()
    assert result.count == 2
    assert result.networks[0].ssid == "MyNetwork"
    assert result.networks[0].rssi == -45


async def test_wifi_scan_in_progress(mock_api: aioresponses) -> None:
    """Test WiFi scan when scan is still in progress."""
    mock_api.get(
        f"{BASE_URL}/system/wifi_scan?refresh=true",
        payload={"networks": [], "count": 0, "scanning": True},
    )
    async with Wattwaechter("192.168.1.100") as client:
        result = await client.wifi_scan(refresh=True)
    assert result.scanning is True
    assert result.count == 0


async def test_timezones(mock_api: aioresponses) -> None:
    """Test timezones endpoint returns list of TimezoneEntry."""
    mock_api.get(
        f"{BASE_URL}/system/timezones",
        payload=[
            {"name": "Europe/Berlin", "gmtOffset": 3600, "daylightOffset": 3600},
            {"name": "America/New_York", "gmtOffset": -18000, "daylightOffset": 3600},
        ],
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.timezones()
    assert len(result) == 2
    assert result[0].name == "Europe/Berlin"
    assert result[0].gmt_offset == 3600
    assert result[0].daylight_offset == 3600
    assert result[1].name == "America/New_York"


async def test_reboot(mock_api: aioresponses) -> None:
    """Test reboot endpoint."""
    mock_api.post(
        f"{BASE_URL}/system/reboot",
        payload={"rebooting": True},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.reboot()
    assert result is True


# --- History / Meter endpoints ---


async def test_meter_data(mock_api: aioresponses) -> None:
    """Test meter data endpoint with short OBIS codes and name field."""
    mock_api.get(
        f"{BASE_URL}/history/latest",
        payload={
            "timestamp": 1709913600,
            "datetime": "2024-03-08T16:00:00",
            "1.8.0": {"value": 12345.678, "unit": "kWh", "name": "Bezug"},
            "2.8.0": {"value": 4567.89, "unit": "kWh", "name": "Einspeisung"},
            "16.7.0": {"value": 1234, "unit": "W", "name": "Leistung"},
            "0.0.0": {"value": "0", "unit": "", "name": "Unbekannt"},
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.meter_data()
    assert result is not None
    assert result.timestamp == 1709913600
    assert result.power == 1234
    assert result.total_consumption == 12345.678
    assert result.total_feed_in == 4567.89
    assert result.get("1.8.0") is not None
    assert result.get("1.8.0").value == 12345.678  # type: ignore[union-attr]
    assert result.get("1.8.0").name == "Bezug"  # type: ignore[union-attr]
    assert result.get("0.0.0").value == "0"  # type: ignore[union-attr]
    assert result.get("nonexistent") is None


async def test_meter_data_no_data(mock_api: aioresponses) -> None:
    """Test meter data returns None on 204."""
    mock_api.get(f"{BASE_URL}/history/latest", status=204)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.meter_data()
    assert result is None


async def test_history_high_res(mock_api: aioresponses) -> None:
    """Test high-resolution history with actual firmware field names."""
    mock_api.get(
        f"{BASE_URL}/history/highRes?date=2024-03-08",
        payload={
            "start": "2024-03-08",
            "days": 1,
            "items": [
                {
                    "date": "2024-03-08T00:00",
                    "timestamp": 1709856000,
                    "import_total_kWh": 12345.0,
                    "export_total_kWh": 4567.0,
                    "import_kW": 0.25,
                    "export_kW": 0.0,
                    "power_W": 1234,
                }
            ],
            "import_total_kWh": 5.6,
            "export_total_kWh": 1.2,
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.history_high_res("2024-03-08")
    assert result.start == "2024-03-08"
    assert result.days == 1
    assert len(result.items) == 1
    assert result.items[0].power_w == 1234
    assert result.items[0].import_total_kwh == 12345.0
    assert result.items[0].import_kw == 0.25
    assert result.import_total_kwh == 5.6
    assert result.export_total_kwh == 1.2


async def test_history_low_res(mock_api: aioresponses) -> None:
    """Test low-resolution history with actual firmware field names."""
    mock_api.get(
        f"{BASE_URL}/history/lowRes?start=2024-03-01&days=2",
        payload={
            "start": "2024-03-01",
            "items": [
                {
                    "date": "2024-03-01",
                    "timestamp": 1709251200,
                    "import_total_kWh": 12340.0,
                    "export_total_kWh": 4560.0,
                    "import_kWh": 8.5,
                    "export_kWh": 2.1,
                },
                {
                    "date": "2024-03-02",
                    "timestamp": 1709337600,
                    "import_total_kWh": 12348.5,
                    "export_total_kWh": 4562.1,
                    "import_kWh": 7.0,
                    "export_kWh": 1.5,
                },
            ],
            "import_total_kWh": 15.5,
            "export_total_kWh": 3.6,
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.history_low_res("2024-03-01", 2)
    assert len(result.items) == 2
    assert result.items[0].import_kwh == 8.5
    assert result.items[1].timestamp == 1709337600
    assert result.import_total_kwh == 15.5
    assert result.export_total_kwh == 3.6


# --- Log endpoints ---


async def test_logs_rawdump(mock_api: aioresponses) -> None:
    """Test raw dump log endpoint returns bytes."""
    raw_bytes = b"\x1b\x1b\x1b\x1b\x01\x01\x01\x01"
    mock_api.get(
        f"{BASE_URL}/logs/rawdump",
        body=raw_bytes,
        content_type="application/octet-stream",
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.logs_rawdump()
    assert result == raw_bytes
    assert isinstance(result, bytes)


async def test_logs_rawdump_no_data(mock_api: aioresponses) -> None:
    """Test raw dump returns None on 204."""
    mock_api.get(f"{BASE_URL}/logs/rawdump", status=204)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.logs_rawdump()
    assert result is None


async def test_logs_persistent(mock_api: aioresponses) -> None:
    """Test persistent log endpoint."""
    csv_data = "timestamp,power,import,export\n1709913600,1234,12345.6,4567.8"
    mock_api.get(
        f"{BASE_URL}/logs/persistent",
        body=csv_data,
        content_type="text/plain",
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.logs_persistent()
    assert "timestamp,power" in result


async def test_logs_ram(mock_api: aioresponses) -> None:
    """Test RAM log endpoint."""
    log_data = "[2024-03-08 16:00:00] INFO: System started"
    mock_api.get(
        f"{BASE_URL}/logs/ram",
        body=log_data,
        content_type="text/plain",
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.logs_ram()
    assert "System started" in result


# --- OTA endpoints ---


async def test_ota_check(mock_api: aioresponses) -> None:
    """Test OTA check endpoint with all fields including url and md5."""
    mock_api.get(
        f"{BASE_URL}/ota/check",
        payload={
            "ok": True,
            "data": {
                "update_available": True,
                "version": "1.2.0",
                "tag": "stable",
                "release_date": "2025-03-01",
                "release_note_de": "Fehlerbehebungen",
                "release_note_en": "Bug fixes",
                "last_checked": 1709913600,
                "url": "https://releases.example.com/fw/1.2.0.bin",
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
            },
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.ota_check()
    assert result.ok is True
    assert result.data.update_available is True
    assert result.data.version == "1.2.0"
    assert result.data.url == "https://releases.example.com/fw/1.2.0.bin"
    assert result.data.md5 == "d41d8cd98f00b204e9800998ecf8427e"


async def test_ota_check_no_update(mock_api: aioresponses) -> None:
    """Test OTA check when no update is available (url/md5 empty)."""
    mock_api.get(
        f"{BASE_URL}/ota/check",
        payload={
            "ok": True,
            "data": {
                "update_available": False,
                "version": "",
                "tag": "",
                "release_date": "",
                "release_note_de": "",
                "release_note_en": "",
                "last_checked": 1709913600,
            },
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.ota_check()
    assert result.data.update_available is False
    assert result.data.url == ""
    assert result.data.md5 == ""


async def test_ota_start(mock_api: aioresponses) -> None:
    """Test OTA start endpoint."""
    mock_api.post(
        f"{BASE_URL}/ota/start",
        payload={"ok": True, "msg": "OTA started"},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.ota_start()
    assert result is True


# --- Settings endpoints ---


async def test_settings(mock_api: aioresponses) -> None:
    """Test settings endpoint."""
    mock_api.get(
        f"{BASE_URL}/settings",
        payload={
            "wifi": {
                "primary": {
                    "enable": True,
                    "ssid": "MyNetwork",
                    "static_ip": False,
                    "ip": "",
                    "subnet": "",
                    "gateway": "",
                    "dns": "",
                },
                "secondary": {
                    "enable": False,
                    "ssid": "",
                    "static_ip": False,
                    "ip": "",
                    "subnet": "",
                    "gateway": "",
                    "dns": "",
                },
            },
            "accessPoint": {
                "enable": True,
                "password_enable": False,
                "ssid": "WattWaechter-1234",
            },
            "mqtt": {
                "enable": False,
                "host": "",
                "port": 8883,
                "use_tls": True,
                "user": "",
                "sendInterval": 60,
                "client_id": "",
                "topic_prefix": "wattwaechter",
            },
            "language": {
                "active": "de",
                "installed": [
                    {"code": "de", "name": "Deutsch"},
                    {"code": "en", "name": "English"},
                ],
            },
            "timezone": "Europe/Berlin",
            "ntp_server": "pool.ntp.org",
            "rebootCounter": 0,
            "rebootsTotal": 5,
            "rebootsAll": 10,
            "ledEnable": True,
            "api_auth_required": True,
            "device_name": "WattWaechter",
            "awsIotEnabled": False,
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.settings()
    assert result.wifi_primary.ssid == "MyNetwork"
    assert result.wifi_primary.enable is True
    assert result.wifi_secondary.enable is False
    assert result.access_point.ssid == "WattWaechter-1234"
    assert result.mqtt.port == 8883
    assert result.mqtt.use_tls is True
    assert result.mqtt.sendInterval == 60
    assert result.language.active == "de"
    assert len(result.language.installed) == 2
    assert result.timezone == "Europe/Berlin"
    assert result.device_name == "WattWaechter"
    assert result.led_enable is True


async def test_settings_mqtt_defaults(mock_api: aioresponses) -> None:
    """Test that MQTT defaults match firmware (port 8883, TLS on, 60s interval)."""
    mock_api.get(
        f"{BASE_URL}/settings",
        payload={
            "wifi": {"primary": {}, "secondary": {}},
            "accessPoint": {},
            "mqtt": {},
            "language": {"active": "de", "installed": []},
        },
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.settings()
    assert result.mqtt.port == 8883
    assert result.mqtt.use_tls is True
    assert result.mqtt.sendInterval == 60


async def test_update_settings(mock_api: aioresponses) -> None:
    """Test update settings endpoint."""
    mock_api.post(
        f"{BASE_URL}/settings",
        payload={"success": True, "applied": {"ledEnable": False}},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.update_settings({"ledEnable": False})
    assert result == {"ledEnable": False}


# --- Auth endpoints ---


async def test_generate_tokens(mock_api: aioresponses) -> None:
    """Test token generation endpoint."""
    mock_api.post(
        f"{BASE_URL}/auth/tokens/generate",
        payload={
            "success": True,
            "pending": {
                "token_read": "A1B2C3D4E5F6G7H8",
                "token_write": "X9Y8Z7W6V5U4T3S2",
            },
            "expires_in": 60,
        },
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.generate_tokens()
    assert result.success is True
    assert result.token_read == "A1B2C3D4E5F6G7H8"
    assert result.token_write == "X9Y8Z7W6V5U4T3S2"
    assert result.expires_in == 60


async def test_confirm_tokens(mock_api: aioresponses) -> None:
    """Test token confirmation endpoint."""
    mock_api.post(
        f"{BASE_URL}/auth/tokens/confirm",
        payload={"success": True, "message": "Tokens activated successfully."},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.confirm_tokens("X9Y8Z7W6V5U4T3S2")
    assert result is True


async def test_setup_token(mock_api: aioresponses) -> None:
    """Test setup token endpoint."""
    mock_api.get(
        f"{BASE_URL}/setup/token",
        payload={"readToken": "READ123", "writeToken": "WRITE456"},
    )
    async with Wattwaechter("192.168.1.100") as client:
        result = await client.setup_token()
    assert result["readToken"] == "READ123"
    assert result["writeToken"] == "WRITE456"


async def test_setup_token_already_complete(mock_api: aioresponses) -> None:
    """Test setup token returns 403 when initial setup is complete."""
    mock_api.get(f"{BASE_URL}/setup/token", status=403)
    async with Wattwaechter("192.168.1.100") as client:
        with pytest.raises(WattwaechterAuthenticationError, match="insufficient permissions"):
            await client.setup_token()


# --- MQTT CA endpoints ---


async def test_mqtt_ca_status(mock_api: aioresponses) -> None:
    """Test MQTT CA status endpoint."""
    mock_api.get(
        f"{BASE_URL}/mqtt/ca",
        payload={"has_custom_cert": False, "bundle_size": 5750, "custom_size": 0},
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        result = await client.mqtt_ca_status()
    assert result.has_custom_cert is False
    assert result.bundle_size == 5750


async def test_mqtt_ca_upload(mock_api: aioresponses) -> None:
    """Test MQTT CA upload returns CaCertActionResponse with all fields."""
    mock_api.post(
        f"{BASE_URL}/mqtt/ca",
        payload={"success": True, "message": "Certificate added", "bundle_size": 7500},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.mqtt_ca_upload("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
    assert result.success is True
    assert result.message == "Certificate added"
    assert result.bundle_size == 7500


async def test_mqtt_ca_delete(mock_api: aioresponses) -> None:
    """Test MQTT CA delete returns CaCertActionResponse with all fields."""
    mock_api.delete(
        f"{BASE_URL}/mqtt/ca",
        payload={"success": True, "message": "Custom certificate deleted", "bundle_size": 5750},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.mqtt_ca_delete()
    assert result.success is True
    assert result.message == "Custom certificate deleted"
    assert result.bundle_size == 5750


async def test_mqtt_ca_delete_not_found(mock_api: aioresponses) -> None:
    """Test MQTT CA delete raises NotFoundError when no custom cert exists."""
    mock_api.delete(f"{BASE_URL}/mqtt/ca", status=404)
    async with Wattwaechter("192.168.1.100", token="write") as client:
        with pytest.raises(WattwaechterNotFoundError):
            await client.mqtt_ca_delete()


# --- Cloud pairing endpoints ---


async def test_cloud_pair(mock_api: aioresponses) -> None:
    """Test cloud pairing endpoint."""
    mock_api.post(
        f"{BASE_URL}/cloud/pair",
        payload={"success": True, "message": "Pairing wird durchgeführt..."},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.cloud_pair("WW-ABCD2345")
    assert result is True


async def test_cloud_unpair(mock_api: aioresponses) -> None:
    """Test cloud unpairing endpoint."""
    mock_api.delete(
        f"{BASE_URL}/cloud/pair",
        payload={"success": True, "message": "Pairing token removed."},
    )
    async with Wattwaechter("192.168.1.100", token="write") as client:
        result = await client.cloud_unpair()
    assert result is True


# --- Error handling ---


async def test_auth_error(mock_api: aioresponses) -> None:
    """Test 401 raises WattwaechterAuthenticationError."""
    mock_api.get(f"{BASE_URL}/system/info", status=401)
    async with Wattwaechter("192.168.1.100", token="bad") as client:
        with pytest.raises(WattwaechterAuthenticationError):
            await client.system_info()


async def test_forbidden_error(mock_api: aioresponses) -> None:
    """Test 403 raises WattwaechterAuthenticationError."""
    mock_api.post(f"{BASE_URL}/system/reboot", status=403)
    async with Wattwaechter("192.168.1.100", token="read") as client:
        with pytest.raises(WattwaechterAuthenticationError, match="insufficient permissions"):
            await client.reboot()


async def test_bad_request_error(mock_api: aioresponses) -> None:
    """Test 400 raises WattwaechterBadRequestError."""
    mock_api.get(f"{BASE_URL}/history/highRes?date=invalid", status=400)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterBadRequestError, match="Bad request"):
            await client.history_high_res("invalid")


async def test_not_found_error(mock_api: aioresponses) -> None:
    """Test 404 raises WattwaechterNotFoundError."""
    mock_api.get(f"{BASE_URL}/logs/persistent", status=404)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterNotFoundError, match="not found"):
            await client.logs_persistent()


async def test_payload_too_large_error(mock_api: aioresponses) -> None:
    """Test 413 raises WattwaechterPayloadTooLargeError."""
    mock_api.post(f"{BASE_URL}/mqtt/ca", status=413)
    async with Wattwaechter("192.168.1.100", token="write") as client:
        with pytest.raises(WattwaechterPayloadTooLargeError):
            await client.mqtt_ca_upload("x" * 5000)


async def test_rate_limit_error(mock_api: aioresponses) -> None:
    """Test 429 raises WattwaechterRateLimitError."""
    mock_api.get(
        f"{BASE_URL}/system/info",
        status=429,
        headers={"Retry-After": "5"},
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterRateLimitError) as exc_info:
            await client.system_info()
    assert exc_info.value.retry_after == 5


async def test_connection_error(mock_api: aioresponses) -> None:
    """Test connection error raises WattwaechterConnectionError."""
    mock_api.get(
        f"{BASE_URL}/system/alive",
        exception=aiohttp.ClientError("Connection refused"),
    )
    async with Wattwaechter("192.168.1.100") as client:
        with pytest.raises(WattwaechterConnectionError):
            await client.alive()


async def test_unexpected_status(mock_api: aioresponses) -> None:
    """Test unexpected status raises WattwaechterConnectionError."""
    mock_api.get(f"{BASE_URL}/system/info", status=500)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterConnectionError, match="Unexpected status 500"):
            await client.system_info()


async def test_service_unavailable(mock_api: aioresponses) -> None:
    """Test 503 raises WattwaechterConnectionError."""
    mock_api.get(
        f"{BASE_URL}/system/info",
        status=503,
        headers={"Retry-After": "1"},
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterConnectionError, match="Device busy"):
            await client.system_info()


async def test_invalid_json_response(mock_api: aioresponses) -> None:
    """Test invalid JSON response raises WattwaechterConnectionError."""
    mock_api.get(
        f"{BASE_URL}/system/alive",
        body="not json",
        content_type="text/html",
    )
    async with Wattwaechter("192.168.1.100") as client:
        with pytest.raises(WattwaechterConnectionError, match="Invalid JSON"):
            await client.alive()


async def test_unexpected_status_text_request(mock_api: aioresponses) -> None:
    """Test unexpected status in text request raises WattwaechterConnectionError."""
    mock_api.get(f"{BASE_URL}/logs/ram", status=500)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterConnectionError, match="Unexpected status 500"):
            await client.logs_ram()


async def test_connection_error_text_request(mock_api: aioresponses) -> None:
    """Test connection error in text request raises WattwaechterConnectionError."""
    mock_api.get(
        f"{BASE_URL}/logs/ram",
        exception=aiohttp.ClientError("Connection refused"),
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterConnectionError):
            await client.logs_ram()


async def test_rawdump_unexpected_status(mock_api: aioresponses) -> None:
    """Test rawdump unexpected status raises WattwaechterConnectionError."""
    mock_api.get(f"{BASE_URL}/logs/rawdump", status=500)
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterConnectionError, match="Unexpected status 500"):
            await client.logs_rawdump()


async def test_timezones_connection_error(mock_api: aioresponses) -> None:
    """Test timezones connection error."""
    mock_api.get(
        f"{BASE_URL}/system/timezones",
        exception=aiohttp.ClientError("Connection refused"),
    )
    async with Wattwaechter("192.168.1.100", token="test") as client:
        with pytest.raises(WattwaechterConnectionError):
            await client.timezones()


# --- Context manager / session ---


async def test_external_session(mock_api: aioresponses) -> None:
    """Test using an external session."""
    import aiohttp

    mock_api.get(
        f"{BASE_URL}/system/alive",
        payload={"alive": True, "version": "1.0.0"},
    )
    async with aiohttp.ClientSession() as session:
        client = Wattwaechter("192.168.1.100", session=session)
        result = await client.alive()
        assert result.alive is True
        # Session should NOT be closed by the client
        await client.close()
        assert not session.closed


async def test_host_property() -> None:
    """Test host property."""
    client = Wattwaechter("192.168.1.100")
    assert client.host == "192.168.1.100"
    await client.close()
