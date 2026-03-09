"""Example: Read current smart meter data from a WattWächter device."""

import asyncio

from aio_wattwaechter import Wattwaechter


async def main() -> None:
    async with Wattwaechter("192.168.1.100") as client:
        data = await client.meter_data()
        if data is None:
            print("No meter data available yet.")
            return

        print(f"Timestamp: {data.datetime_str}")
        print(f"Power:     {data.power} W")
        print(f"Import:    {data.total_consumption} kWh")
        print(f"Export:    {data.total_feed_in} kWh")
        print()
        print("All OBIS values:")
        for code, val in data.values.items():
            print(f"  {code}: {val.value} {val.unit} ({val.name})")


if __name__ == "__main__":
    asyncio.run(main())
