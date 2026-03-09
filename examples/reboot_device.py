"""Example: Reboot the device (requires WRITE token)."""

import asyncio
import sys

from aio_wattwaechter import Wattwaechter, WattwaechterConnectionError

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.100"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None


async def main() -> None:
    async with Wattwaechter(HOST, token=TOKEN) as client:
        alive = await client.alive()
        print(f"Device online: v{alive.version}")

        print("Rebooting...")
        result = await client.reboot()
        print(f"Reboot initiated: {result}")

        # Wait for the device to come back online
        print("Waiting for device to restart...")
        await asyncio.sleep(10)

        for attempt in range(12):
            try:
                alive = await client.alive()
                print(f"Device back online: v{alive.version}")
                return
            except WattwaechterConnectionError:
                await asyncio.sleep(5)

        print("Device did not come back online within 60 seconds.")


asyncio.run(main())
