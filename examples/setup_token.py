"""Example: Get initial setup tokens (only works before first WiFi connection).

This endpoint is only available during the initial device setup via the
access point. Once WiFi has been configured, it returns 403.
"""

import asyncio
import sys

from aio_wattwaechter import Wattwaechter, WattwaechterAuthenticationError

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.4.1"


async def main() -> None:
    # No token needed — this is the initial setup endpoint
    async with Wattwaechter(HOST) as client:
        try:
            tokens = await client.setup_token()
            print("Initial setup tokens:")
            print(f"  Read token:  {tokens['readToken']}")
            print(f"  Write token: {tokens['writeToken']}")
            print("\nSave these tokens! They are needed for authenticated access.")
        except WattwaechterAuthenticationError:
            print("Initial setup is already complete (403).")
            print("Use generate_tokens() with a WRITE token to rotate tokens.")


asyncio.run(main())
