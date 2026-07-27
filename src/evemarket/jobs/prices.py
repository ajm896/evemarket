from evemarket.esi import ESIClient
from evemarket.esi.config import make_client
from evemarket.models import Price


async def pull_prices():
    async with make_client() as client:
        esi = ESIClient(client)
        prices: list[Price] = await esi.market_prices()
        for p in prices:
            print(p)
