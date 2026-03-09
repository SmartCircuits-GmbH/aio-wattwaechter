"""Example: Download device logs.

Demonstrates logs_ram(), logs_persistent(), and logs_rawdump().
"""

import asyncio
import sys

from aio_wattwaechter import Wattwaechter

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.100"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None


async def main() -> None:
    async with Wattwaechter(HOST, token=TOKEN) as client:
        # RAM log — current log snapshot from memory
        ram = await client.logs_ram()
        if ram:
            print(f"=== RAM Log ({len(ram)} chars) ===")
            for line in ram.strip().splitlines()[:10]:
                print(f"  {line}")
            if ram.count("\n") > 10:
                print(f"  ... ({ram.count(chr(10))} lines total)")
        else:
            print("RAM log is empty.")

        # Persistent log — CSV log file from flash storage
        persistent = await client.logs_persistent()
        if persistent:
            print(f"\n=== Persistent Log ({len(persistent)} chars) ===")
            for line in persistent.strip().splitlines()[:5]:
                print(f"  {line}")
        else:
            print("\nPersistent log is empty.")

        # Raw dump — binary SML data from smart meter buffer
        raw = await client.logs_rawdump()
        if raw:
            print(f"\n=== Raw Dump ({len(raw)} bytes) ===")
            print(f"  First 32 bytes: {raw[:32].hex()}")
            # Save to file:
            # with open("rawdump.bin", "wb") as f:
            #     f.write(raw)
        else:
            print("\nNo raw dump available.")


asyncio.run(main())
