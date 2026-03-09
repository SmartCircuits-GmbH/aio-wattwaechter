"""Example: Manage custom MQTT CA certificates.

Note: Uploading/deleting certificates requires a WRITE token when authentication is enabled.
"""

import asyncio
from pathlib import Path

from aio_wattwaechter import Wattwaechter


async def main() -> None:
    # Pass token="your-write-token" if authentication is enabled
    async with Wattwaechter("192.168.1.100") as client:
        # Check current status
        status = await client.mqtt_ca_status()
        print(f"Custom certificate: {'yes' if status.has_custom_cert else 'no'}")
        print(f"Bundle size: {status.bundle_size} bytes")
        print(f"Custom size: {status.custom_size} bytes")
        print()

        if not status.has_custom_cert:
            # Upload a custom CA certificate
            cert_path = Path("my-mqtt-ca.pem")
            if cert_path.exists():
                cert = cert_path.read_text()
                result = await client.mqtt_ca_upload(cert)
                print(f"Upload: {'success' if result.success else 'failed'}")
                print(f"Bundle size: {result.bundle_size} bytes")
            else:
                print(f"Certificate file not found: {cert_path}")
        else:
            # Optionally delete the custom certificate
            confirm = input("Delete custom certificate? (y/N): ")
            if confirm.lower() == "y":
                result = await client.mqtt_ca_delete()
                print(f"Delete: {'success' if result.success else 'failed'}")


if __name__ == "__main__":
    asyncio.run(main())
