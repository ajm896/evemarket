from datetime import UTC, datetime

from evemarket.esi import ESIClient
from evemarket.esi.config import make_client
from evemarket.storage import DB_PATH, ensure_schema, insert_prices, make_connection


async def pull_prices():
    async with make_client() as client:
        esi = ESIClient(client)
        payload = await esi.market_prices()

    pulled_at = datetime.now(UTC)
    with make_connection() as conn:
        ensure_schema(conn)
        count = insert_prices(conn, payload, pulled_at)

    print(f"Inserted {count} rows into {DB_PATH} at {pulled_at}")
