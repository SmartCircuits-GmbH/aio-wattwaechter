"""Example: Retrieve energy history data."""

import asyncio
from datetime import date, timedelta

from aio_wattwaechter import Wattwaechter


async def main() -> None:
    async with Wattwaechter("192.168.1.100") as client:
        # High-resolution data (15-min intervals) for today
        today = date.today().isoformat()
        print(f"High-res data for {today}:")
        high_res = await client.history_high_res(today)
        for item in high_res.items[:5]:  # Show first 5 entries
            print(f"  {item.date}: {item.power_w}W, import +{item.import_kw}kW, export +{item.export_kw}kW")
        print(f"  ... ({len(high_res.items)} entries total)")
        print(f"  Total: import={high_res.import_total_kwh}kWh, export={high_res.export_total_kwh}kWh")
        print()

        # Low-resolution data (daily) for the last 7 days
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        print(f"Daily data from {week_ago} (7 days):")
        low_res = await client.history_low_res(week_ago, 7)
        for item in low_res.items:
            print(f"  {item.date}: import +{item.import_kwh}kWh, export +{item.export_kwh}kWh")
        print(f"  Total: import={low_res.import_total_kwh}kWh, export={low_res.export_total_kwh}kWh")


if __name__ == "__main__":
    asyncio.run(main())
