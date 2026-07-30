import asyncio

from httpx import AsyncClient

class ESIClient:
    def __init__(self, client: AsyncClient):
        self._client: AsyncClient = client
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(30)

    async def market_prices(self, etag: str) -> tuple[bytes, str] | tuple[None, None]:
        async with self._semaphore:
            headers = {
                    "If-None-Match": etag
                    }
            response = await self._client.get("/markets/prices", headers=headers)
            headers = response.headers
            if response.status_code == 304:
                return None, None
            _ = response.raise_for_status()
        return response.content, headers.get("ETag", "N/A")

    async def character_assets(self, character_id: int, access_token: str, page: int = 1) -> tuple[bytes, int]:
        async with self._semaphore:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await self._client.get(
                f"/characters/{character_id}/assets", headers=headers, params={"page": page}
            )
            _ = response.raise_for_status()
        return response.content, int(response.headers.get("X-Pages", 1))
