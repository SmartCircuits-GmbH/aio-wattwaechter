"""Example: List supported timezones."""

import asyncio
import sys

from aio_wattwaechter import Wattwaechter

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.100"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None


async def main() -> None:
    async with Wattwaechter(HOST, token=TOKEN) as client:
        timezones = await client.timezones()
        print(f"Supported timezones ({len(timezones)}):\n")
        for tz in timezones:
            gmt_hours = tz.gmt_offset / 3600
            dst_hours = tz.daylight_offset / 3600
            print(f"  {tz.name:<30} GMT{gmt_hours:+.0f}  DST{dst_hours:+.0f}")


asyncio.run(main())
