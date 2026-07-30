import asyncio

from httpx import AsyncClient


class ESIClient:
    def __init__(self, client: AsyncClient):
        self._client: AsyncClient = client
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(30)

    async def market_prices(self) -> bytes:
        async with self._semaphore:
            response = await self._client.get("/markets/prices")
            response.raise_for_status()
        return response.content
