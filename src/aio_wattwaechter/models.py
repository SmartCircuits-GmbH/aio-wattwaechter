"""Data models for the WattWächter API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


# --- System models ---


@dataclass(frozen=True)
class AliveResponse:
    """Response from GET /system/alive."""

    alive: bool
    version: str


@dataclass(frozen=True)
class InfoEntry:
    """Single entry in a system info section."""

    name: str
    value: str
    unit: str


@dataclass(frozen=True)
class SystemInfo:
    """Response from GET /system/info."""

    uptime: list[InfoEntry]
    wifi: list[InfoEntry]
    ap: list[InfoEntry]
    esp: list[InfoEntry]
    heap: list[InfoEntry]

    def get_value(self, section: str, name: str) -> str | None:
        """Get a value by section and name."""
        entries: list[InfoEntry] = getattr(self, section, [])
        for entry in entries:
            if entry.name == name:
                return entry.value
        return None


class LedStatus(StrEnum):
    """LED status codes."""

    NONE = "NONE"
    OK = "OK"
    STARTUP = "STARTUP"
    INFO = "INFO"
    BLE_ACTIVE = "BLE_ACTIVE"
    BLE_CONNECTED = "BLE_CONNECTED"
    OTA_ACTIVE = "OTA_ACTIVE"
    ERROR = "ERROR"
    RESET_PENDING = "RESET_PENDING"


class LedColor(StrEnum):
    """LED colors."""

    OFF = "off"
    GREEN = "green"
    YELLOW = "yellow"
    BLUE = "blue"
    MAGENTA = "magenta"
    RED = "red"


class LedMode(StrEnum):
    """LED display modes."""

    SOLID = "solid"
    PULSE = "pulse"
    DIMMED = "dimmed"
    OFF = "off"


@dataclass(frozen=True)
class RgbColor:
    """RGB color value."""

    r: int
    g: int
    b: int


@dataclass(frozen=True)
class LedInfo:
    """Response from GET /system/led."""

    status: LedStatus
    priority: int
    color: LedColor
    mode: LedMode
    rgb: RgbColor
    enabled: bool
    active_statuses: dict[str, bool]


@dataclass(frozen=True)
class SelfTestResult:
    """Response from POST /system/selftest."""

    success: bool
    result: str
    message: str


@dataclass(frozen=True)
class WifiNetwork:
    """A discovered WiFi network."""

    ssid: str
    rssi: int


@dataclass(frozen=True)
class WifiScanResponse:
    """Response from GET /system/wifi_scan."""

    networks: list[WifiNetwork]
    count: int
    scanning: bool = False


@dataclass(frozen=True)
class TimezoneEntry:
    """A supported timezone."""

    name: str
    gmt_offset: int
    daylight_offset: int


# --- History / Meter models ---


@dataclass(frozen=True)
class ObisValue:
    """A single OBIS code value from the smart meter."""

    value: float | str
    unit: str
    name: str


@dataclass(frozen=True)
class MeterData:
    """Response from GET /history/latest."""

    timestamp: int
    datetime_str: str
    values: dict[str, ObisValue]

    def get(self, obis_code: str) -> ObisValue | None:
        """Get a value by OBIS code (e.g. '16.7.0')."""
        return self.values.get(obis_code)

    def _as_float(self, obis_code: str) -> float | None:
        """Get a numeric OBIS value as float, or None."""
        val = self.get(obis_code)
        if val is None:
            return None
        try:
            return float(val.value)
        except (ValueError, TypeError):
            return None

    @property
    def power(self) -> float | None:
        """Total active power in W (OBIS 16.7.0)."""
        return self._as_float("16.7.0")

    @property
    def total_consumption(self) -> float | None:
        """Total consumption in kWh (OBIS 1.8.0)."""
        return self._as_float("1.8.0")

    @property
    def total_feed_in(self) -> float | None:
        """Total feed-in in kWh (OBIS 2.8.0)."""
        return self._as_float("2.8.0")


@dataclass(frozen=True)
class HighResEntry:
    """A single entry in high-resolution history data."""

    date: str
    timestamp: int
    import_total_kwh: float
    export_total_kwh: float
    import_kw: float
    export_kw: float
    power_w: float


@dataclass(frozen=True)
class HighResHistory:
    """Response from GET /history/highRes."""

    start: str
    days: int
    items: list[HighResEntry]
    import_total_kwh: float
    export_total_kwh: float


@dataclass(frozen=True)
class LowResEntry:
    """A single entry in low-resolution history data."""

    date: str
    timestamp: int
    import_total_kwh: float
    export_total_kwh: float
    import_kwh: float
    export_kwh: float


@dataclass(frozen=True)
class LowResHistory:
    """Response from GET /history/lowRes."""

    start: str
    items: list[LowResEntry]
    import_total_kwh: float
    export_total_kwh: float


# --- OTA models ---


@dataclass(frozen=True)
class OtaData:
    """OTA update information."""

    update_available: bool
    version: str
    tag: str
    release_date: str
    release_note_de: str
    release_note_en: str
    last_checked: int
    url: str
    md5: str


@dataclass(frozen=True)
class OtaCheckResponse:
    """Response from GET /ota/check."""

    ok: bool
    data: OtaData


# --- Settings models ---


@dataclass(frozen=True)
class WifiConfig:
    """WiFi network configuration."""

    enable: bool
    ssid: str
    static_ip: bool
    ip: str
    subnet: str
    gateway: str
    dns: str


@dataclass(frozen=True)
class AccessPointConfig:
    """Access point configuration."""

    enable: bool
    password_enable: bool
    ssid: str


@dataclass(frozen=True)
class MqttConfig:
    """MQTT configuration."""

    enable: bool
    host: str
    port: int
    use_tls: bool
    user: str
    sendInterval: int
    client_id: str
    topic_prefix: str


@dataclass(frozen=True)
class LanguageEntry:
    """An installed language."""

    code: str
    name: str


@dataclass(frozen=True)
class LanguageConfig:
    """Language configuration."""

    active: str
    installed: list[LanguageEntry]


@dataclass(frozen=True)
class Settings:
    """Response from GET /settings."""

    wifi_primary: WifiConfig
    wifi_secondary: WifiConfig
    access_point: AccessPointConfig
    mqtt: MqttConfig
    language: LanguageConfig
    timezone: str
    ntp_server: str
    reboot_counter: int
    reboots_total: int
    reboots_all: int
    led_enable: bool
    api_auth_required: bool
    device_name: str
    aws_iot_enabled: bool


# --- Auth models ---


@dataclass(frozen=True)
class TokenGenerateResponse:
    """Response from POST /auth/tokens/generate."""

    success: bool
    token_read: str
    token_write: str
    expires_in: int


# --- MQTT CA models ---


@dataclass(frozen=True)
class CaCertStatus:
    """Response from GET /mqtt/ca."""

    has_custom_cert: bool
    bundle_size: int
    custom_size: int


@dataclass(frozen=True)
class CaCertActionResponse:
    """Response from POST/DELETE /mqtt/ca."""

    success: bool
    message: str
    bundle_size: int


# --- Parsing helpers ---


def _parse_alive(data: dict[str, Any]) -> AliveResponse:
    """Parse alive response."""
    return AliveResponse(alive=data["alive"], version=data["version"])


def _parse_info_entries(items: list[dict[str, Any]]) -> list[InfoEntry]:
    """Parse a list of info entries."""
    return [
        InfoEntry(
            name=item["name"],
            value=str(item["value"]),
            unit=item.get("unit", ""),
        )
        for item in items
    ]


def _parse_system_info(data: dict[str, Any]) -> SystemInfo:
    """Parse system info response."""
    return SystemInfo(
        uptime=_parse_info_entries(data.get("uptime", [])),
        wifi=_parse_info_entries(data.get("wifi", [])),
        ap=_parse_info_entries(data.get("ap", [])),
        esp=_parse_info_entries(data.get("esp", [])),
        heap=_parse_info_entries(data.get("heap", [])),
    )


def _parse_led_info(data: dict[str, Any]) -> LedInfo:
    """Parse LED info response."""
    rgb = data.get("rgb", {})
    return LedInfo(
        status=LedStatus(data["status"]),
        priority=data["priority"],
        color=LedColor(data["color"]),
        mode=LedMode(data["mode"]),
        rgb=RgbColor(r=rgb.get("r", 0), g=rgb.get("g", 0), b=rgb.get("b", 0)),
        enabled=data["enabled"],
        active_statuses=data.get("active_statuses", {}),
    )


def _parse_self_test(data: dict[str, Any]) -> SelfTestResult:
    """Parse self-test response."""
    return SelfTestResult(
        success=data["success"],
        result=data["result"],
        message=data["message"],
    )


def _parse_wifi_scan(data: dict[str, Any]) -> WifiScanResponse:
    """Parse WiFi scan response."""
    return WifiScanResponse(
        networks=[
            WifiNetwork(ssid=n["ssid"], rssi=n["rssi"])
            for n in data.get("networks", [])
        ],
        count=data.get("count", 0),
        scanning=data.get("scanning", False),
    )


def _parse_timezones(data: list[dict[str, Any]]) -> list[TimezoneEntry]:
    """Parse timezones response."""
    return [
        TimezoneEntry(
            name=tz["name"],
            gmt_offset=tz["gmtOffset"],
            daylight_offset=tz["daylightOffset"],
        )
        for tz in data
    ]


def _parse_meter_data(data: dict[str, Any]) -> MeterData:
    """Parse meter data response."""
    values: dict[str, ObisValue] = {}
    timestamp = data.get("timestamp", 0)
    datetime_str = data.get("datetime", "")
    for key, val in data.items():
        if key in ("timestamp", "datetime"):
            continue
        if isinstance(val, dict) and "value" in val:
            values[key] = ObisValue(
                value=val["value"],
                unit=val.get("unit", ""),
                name=val.get("name", ""),
            )
    return MeterData(
        timestamp=timestamp,
        datetime_str=datetime_str,
        values=values,
    )


def _parse_high_res_history(data: dict[str, Any]) -> HighResHistory:
    """Parse high-resolution history response."""
    return HighResHistory(
        start=data["start"],
        days=data.get("days", 1),
        items=[
            HighResEntry(
                date=item["date"],
                timestamp=item["timestamp"],
                import_total_kwh=item["import_total_kWh"],
                export_total_kwh=item["export_total_kWh"],
                import_kw=item.get("import_kW", 0.0),
                export_kw=item.get("export_kW", 0.0),
                power_w=item.get("power_W", 0.0),
            )
            for item in data.get("items", [])
        ],
        import_total_kwh=data.get("import_total_kWh", 0.0),
        export_total_kwh=data.get("export_total_kWh", 0.0),
    )


def _parse_low_res_history(data: dict[str, Any]) -> LowResHistory:
    """Parse low-resolution history response."""
    return LowResHistory(
        start=data["start"],
        items=[
            LowResEntry(
                date=item["date"],
                timestamp=item.get("timestamp", 0),
                import_total_kwh=item.get("import_total_kWh", 0.0),
                export_total_kwh=item.get("export_total_kWh", 0.0),
                import_kwh=item.get("import_kWh", 0.0),
                export_kwh=item.get("export_kWh", 0.0),
            )
            for item in data.get("items", [])
        ],
        import_total_kwh=data.get("import_total_kWh", 0.0),
        export_total_kwh=data.get("export_total_kWh", 0.0),
    )


def _parse_ota_check(data: dict[str, Any]) -> OtaCheckResponse:
    """Parse OTA check response."""
    ota = data.get("data", {})
    return OtaCheckResponse(
        ok=data["ok"],
        data=OtaData(
            update_available=ota.get("update_available", False),
            version=ota.get("version", ""),
            tag=ota.get("tag", ""),
            release_date=ota.get("release_date", ""),
            release_note_de=ota.get("release_note_de", ""),
            release_note_en=ota.get("release_note_en", ""),
            last_checked=ota.get("last_checked", 0),
            url=ota.get("url", ""),
            md5=ota.get("md5", ""),
        ),
    )


def _parse_wifi_config(data: dict[str, Any]) -> WifiConfig:
    """Parse a WiFi config block."""
    return WifiConfig(
        enable=data.get("enable", False),
        ssid=data.get("ssid", ""),
        static_ip=data.get("static_ip", False),
        ip=data.get("ip", ""),
        subnet=data.get("subnet", ""),
        gateway=data.get("gateway", ""),
        dns=data.get("dns", ""),
    )


def _parse_settings(data: dict[str, Any]) -> Settings:
    """Parse settings response."""
    wifi = data.get("wifi", {})
    ap = data.get("accessPoint", {})
    mqtt = data.get("mqtt", {})
    lang = data.get("language", {})
    return Settings(
        wifi_primary=_parse_wifi_config(wifi.get("primary", {})),
        wifi_secondary=_parse_wifi_config(wifi.get("secondary", {})),
        access_point=AccessPointConfig(
            enable=ap.get("enable", False),
            password_enable=ap.get("password_enable", False),
            ssid=ap.get("ssid", ""),
        ),
        mqtt=MqttConfig(
            enable=mqtt.get("enable", False),
            host=mqtt.get("host", ""),
            port=mqtt.get("port", 8883),
            use_tls=mqtt.get("use_tls", True),
            user=mqtt.get("user", ""),
            sendInterval=mqtt.get("sendInterval", 60),
            client_id=mqtt.get("client_id", ""),
            topic_prefix=mqtt.get("topic_prefix", ""),
        ),
        language=LanguageConfig(
            active=lang.get("active", ""),
            installed=[
                LanguageEntry(code=l["code"], name=l["name"])
                for l in lang.get("installed", [])
            ],
        ),
        timezone=data.get("timezone", ""),
        ntp_server=data.get("ntp_server", ""),
        reboot_counter=data.get("rebootCounter", 0),
        reboots_total=data.get("rebootsTotal", 0),
        reboots_all=data.get("rebootsAll", 0),
        led_enable=data.get("ledEnable", True),
        api_auth_required=data.get("api_auth_required", True),
        device_name=data.get("device_name", ""),
        aws_iot_enabled=data.get("awsIotEnabled", False),
    )


def _parse_token_generate(data: dict[str, Any]) -> TokenGenerateResponse:
    """Parse token generate response."""
    pending = data.get("pending", {})
    return TokenGenerateResponse(
        success=data["success"],
        token_read=pending["token_read"],
        token_write=pending["token_write"],
        expires_in=data.get("expires_in", 60),
    )


def _parse_ca_cert_status(data: dict[str, Any]) -> CaCertStatus:
    """Parse CA certificate status response."""
    return CaCertStatus(
        has_custom_cert=data["has_custom_cert"],
        bundle_size=data["bundle_size"],
        custom_size=data["custom_size"],
    )


def _parse_ca_cert_action(data: dict[str, Any]) -> CaCertActionResponse:
    """Parse CA certificate upload/delete response."""
    return CaCertActionResponse(
        success=data.get("success", False),
        message=data.get("message", ""),
        bundle_size=data.get("bundle_size", 0),
    )
