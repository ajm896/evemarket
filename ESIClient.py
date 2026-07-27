from httpx import AsyncClient
import asyncio
from models.price import Price
import msgspec

class ESIClient:
    def __init__(self, client: AsyncClient):
        self._client: AsyncClient = client
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(30)

    async def market_prices(self) -> list[Price]:
        async with self._semaphore:
            response = await self._client.get("/markets/prices")
        return msgspec.json.decode(response.content, type=list[Price])

