"""Live integration test against a real WattWächter device.

Usage:
    python test_live.py [HOST] [TOKEN]

Default host: 192.168.178.116
"""

from __future__ import annotations

import asyncio
import sys
import time

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterBadRequestError,
    WattwaechterNotFoundError,
)

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.178.116"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None

passed = 0
failed = 0
skipped = 0


def ok(name: str, detail: str = "") -> None:
    global passed
    passed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  \033[32m✓\033[0m {name}{suffix}")


def fail(name: str, err: Exception) -> None:
    global failed
    failed += 1
    print(f"  \033[31m✗\033[0m {name}: {err}")


def skip(name: str, reason: str) -> None:
    global skipped
    skipped += 1
    print(f"  \033[33m-\033[0m {name}: {reason}")


async def main() -> None:
    print(f"\n{'='*60}")
    print(f"  WattWächter Live Test — {HOST}")
    print(f"  Auth: {'token provided' if TOKEN else 'no token'}")
    print(f"{'='*60}\n")

    async with Wattwaechter(HOST, token=TOKEN) as client:

        # ── System endpoints ──────────────────────────────────────

        print("System:")

        # alive (no auth required)
        try:
            result = await client.alive()
            assert result.alive is True
            assert isinstance(result.version, str) and len(result.version) > 0
            ok("alive", f"v{result.version}")
        except Exception as e:
            fail("alive", e)
            print("\n  Device not reachable. Aborting.")
            return

        firmware_version = result.version

        # system_info
        try:
            info = await client.system_info()
            assert len(info.uptime) > 0
            assert len(info.wifi) > 0
            assert len(info.esp) > 0
            assert len(info.heap) > 0
            uptime = info.get_value("uptime", "Uptime") or "?"
            rssi = info.get_value("wifi", "RSSI") or "?"
            ok("system_info", f"uptime={uptime}, RSSI={rssi}")
        except Exception as e:
            fail("system_info", e)

        # led
        try:
            led = await client.led()
            assert led.status is not None
            assert led.color is not None
            assert led.mode is not None
            assert isinstance(led.enabled, bool)
            assert isinstance(led.rgb.r, int)
            ok("led", f"{led.color}/{led.mode} status={led.status} enabled={led.enabled}")
        except Exception as e:
            fail("led", e)

        # wifi_scan (no refresh, just read cached)
        try:
            scan = await client.wifi_scan()
            assert isinstance(scan.count, int)
            assert isinstance(scan.networks, list)
            if scan.count > 0:
                assert len(scan.networks[0].ssid) > 0
            ok("wifi_scan", f"{scan.count} networks")
        except Exception as e:
            fail("wifi_scan", e)

        # timezones
        try:
            tz = await client.timezones()
            assert isinstance(tz, list)
            assert any(t.name == "Europe/Berlin" for t in tz)
            ok("timezones", f"{len(tz)} zones")
        except Exception as e:
            fail("timezones", e)

        # selftest (takes ~2s)
        try:
            st = await client.selftest()
            assert isinstance(st.success, bool)
            assert isinstance(st.result, str)
            assert isinstance(st.message, str)
            ok("selftest", f"success={st.success} result={st.result}")
        except Exception as e:
            fail("selftest", e)

        # ── History / Meter endpoints ─────────────────────────────

        print("\nHistory / Meter:")

        # meter_data (latest)
        try:
            meter = await client.meter_data()
            if meter is None:
                skip("meter_data", "no data yet (204)")
            else:
                assert meter.timestamp > 0
                assert isinstance(meter.datetime_str, str)
                assert len(meter.values) > 0
                power = meter.power
                consumption = meter.total_consumption
                feed_in = meter.total_feed_in
                ok("meter_data", f"power={power}W, consumption={consumption}kWh, feed_in={feed_in}kWh, {len(meter.values)} OBIS values")
        except Exception as e:
            fail("meter_data", e)

        # history_high_res (today)
        try:
            today = time.strftime("%Y-%m-%d")
            hr = await client.history_high_res(today)
            assert hr.start == today
            assert isinstance(hr.items, list)
            if len(hr.items) > 0:
                assert hr.items[0].timestamp > 0
            ok("history_high_res", f"{len(hr.items)} entries, import={hr.import_total_kwh:.2f}kWh")
        except WattwaechterBadRequestError:
            skip("history_high_res", "no data for today (400)")
        except Exception as e:
            fail("history_high_res", e)

        # history_low_res (last 7 days)
        try:
            start = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
            lr = await client.history_low_res(start, 7)
            assert isinstance(lr.items, list)
            ok("history_low_res", f"{len(lr.items)} days, import={lr.import_total_kwh:.2f}kWh")
        except WattwaechterBadRequestError:
            skip("history_low_res", "no data for range (400)")
        except Exception as e:
            fail("history_low_res", e)

        # ── Log endpoints ─────────────────────────────────────────

        print("\nLogs:")

        # logs_rawdump
        try:
            raw = await client.logs_rawdump()
            if raw is None:
                skip("logs_rawdump", "no data (204)")
            else:
                assert isinstance(raw, bytes)
                ok("logs_rawdump", f"{len(raw)} bytes")
        except WattwaechterNotFoundError:
            skip("logs_rawdump", "not available (404)")
        except Exception as e:
            fail("logs_rawdump", e)

        # logs_persistent
        try:
            log = await client.logs_persistent()
            lines = log.count("\n") if log else 0
            ok("logs_persistent", f"{len(log)} chars, {lines} lines")
        except WattwaechterNotFoundError:
            skip("logs_persistent", "no log file (404)")
        except Exception as e:
            fail("logs_persistent", e)

        # logs_ram
        try:
            ram = await client.logs_ram()
            lines = ram.count("\n") if ram else 0
            ok("logs_ram", f"{len(ram)} chars, {lines} lines")
        except WattwaechterNotFoundError:
            skip("logs_ram", "not available (404)")
        except Exception as e:
            fail("logs_ram", e)

        # ── OTA endpoints ─────────────────────────────────────────

        print("\nOTA:")

        # ota_check
        try:
            ota = await client.ota_check()
            assert isinstance(ota.ok, bool)
            if ota.data.update_available:
                detail = f"v{ota.data.version}"
                if ota.data.url:
                    detail += f", url={ota.data.url[:60]}"
                if ota.data.md5:
                    detail += f", md5={ota.data.md5[:16]}..."
                ok("ota_check", f"update available: {detail}")
            else:
                ok("ota_check", f"up to date (v{firmware_version})")
        except Exception as e:
            fail("ota_check", e)

        # ota_start — SKIPPED (would actually update!)
        skip("ota_start", "skipped (destructive)")

        # ── Settings endpoints ────────────────────────────────────

        print("\nSettings:")

        # settings
        try:
            s = await client.settings()
            assert isinstance(s.device_name, str)
            assert isinstance(s.timezone, str)
            assert isinstance(s.mqtt.port, int)
            assert isinstance(s.mqtt.use_tls, bool)
            assert isinstance(s.wifi_primary.ssid, str)
            assert isinstance(s.access_point.ssid, str)
            assert isinstance(s.language.active, str)
            assert isinstance(s.led_enable, bool)
            assert isinstance(s.api_auth_required, bool)
            assert isinstance(s.aws_iot_enabled, bool)
            ok("settings", (
                f"name={s.device_name}, tz={s.timezone}, "
                f"mqtt={'on' if s.mqtt.enable else 'off'}:{s.mqtt.port}, "
                f"auth={'on' if s.api_auth_required else 'off'}, "
                f"led={'on' if s.led_enable else 'off'}"
            ))
        except Exception as e:
            fail("settings", e)

        # update_settings — safe round-trip test (read → write same value → verify)
        # Small delay to avoid rate limiting from prior requests
        await asyncio.sleep(1)
        if TOKEN:
            try:
                current = await client.settings()
                # Toggle LED off and back on (harmless)
                original_led = current.led_enable
                applied = await client.update_settings({"ledEnable": not original_led})
                assert "ledEnable" in applied
                # Restore original value
                await client.update_settings({"ledEnable": original_led})
                ok("update_settings", f"toggled LED {original_led} → {not original_led} → {original_led}")
            except Exception as e:
                fail("update_settings", e)
        else:
            skip("update_settings", "no token provided")

        # ── Auth endpoints ────────────────────────────────────────

        print("\nAuth:")

        # setup_token (should fail with 403 if already set up)
        try:
            tokens = await client.setup_token()
            ok("setup_token", f"readToken={tokens.get('readToken', '?')[:8]}...")
        except WattwaechterAuthenticationError:
            ok("setup_token", "403 as expected (setup complete)")
        except Exception as e:
            fail("setup_token", e)

        # generate_tokens — SKIPPED (would invalidate current tokens after confirm)
        skip("generate_tokens", "skipped (would rotate tokens)")
        skip("confirm_tokens", "skipped (would rotate tokens)")

        # ── MQTT CA endpoints ─────────────────────────────────────

        print("\nMQTT CA:")

        # mqtt_ca_status
        try:
            ca = await client.mqtt_ca_status()
            assert isinstance(ca.bundle_size, int)
            assert isinstance(ca.custom_size, int)
            assert isinstance(ca.has_custom_cert, bool)
            ok("mqtt_ca_status", f"custom={ca.has_custom_cert}, bundle={ca.bundle_size}B, custom_size={ca.custom_size}B")
        except Exception as e:
            fail("mqtt_ca_status", e)

        # mqtt_ca_delete (test 404 case — should fail if no custom cert)
        if TOKEN:
            try:
                result = await client.mqtt_ca_delete()
                ok("mqtt_ca_delete", f"success={result.success}, msg={result.message}")
            except WattwaechterNotFoundError:
                ok("mqtt_ca_delete", "404 as expected (no custom cert)")
            except Exception as e:
                fail("mqtt_ca_delete", e)
        else:
            skip("mqtt_ca_delete", "no token provided")

        # mqtt_ca_upload — SKIPPED (would modify cert store)
        skip("mqtt_ca_upload", "skipped (would modify cert store)")

        # ── Cloud endpoints ───────────────────────────────────────

        print("\nCloud:")

        # cloud_pair — SKIPPED (would pair with cloud)
        skip("cloud_pair", "skipped (would modify cloud state)")

        # cloud_unpair — SKIPPED (would unpair from cloud)
        skip("cloud_unpair", "skipped (would modify cloud state)")

        # ── Reboot (last test!) ───────────────────────────────────

        print("\nReboot:")

        if TOKEN:
            try:
                result = await client.reboot()
                assert result is True
                ok("reboot", "device is rebooting")
            except Exception as e:
                fail("reboot", e)
        else:
            skip("reboot", "no token provided")

    # ── Summary ───────────────────────────────────────────────

    print(f"\n{'='*60}")
    total = passed + failed + skipped
    color = "\033[32m" if failed == 0 else "\033[31m"
    print(f"  {color}{passed} passed\033[0m, "
          f"\033[31m{failed} failed\033[0m, "
          f"\033[33m{skipped} skipped\033[0m "
          f"({total} total)")
    print(f"{'='*60}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
