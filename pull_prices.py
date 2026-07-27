from __future__ import annotations
import asyncio
from ESIClient import ESIClient
from models.price import Price
from httpx import AsyncClient

# Start Main
async def pull_prices():
    client = AsyncClient(
        base_url="https://esi.evetech.net",
        timeout=30,
        headers={
            "User-Agent": "EveMarketData/0.1 (AJ; aj@example.com)",
            "X-Compatibility-Date": "2026-07-21",
            "Accept-Language": "en",
        },
    ) 

    async with client:
            esi = ESIClient(client)
            prices: list[Price] = await esi.market_prices()
            for p in prices:
                print(p)
# End Main

if __name__ == '__main__':
    asyncio.run(pull_prices())
