from datetime import UTC, datetime

from evemarket.esi import ESIClient
from evemarket.esi.config import make_client
from evemarket.storage import DB_PATH, ensure_schema, insert_prices, make_connection


async def pull_prices():
    with make_connection() as conn:
        curr_etag_row = conn.sql("SELECT etag FROM market_prices ORDER BY pulled_at DESC LIMIT 1;").fetchone()
        curr_etag = curr_etag_row[0] if curr_etag_row else "N/A"

        async with make_client() as client:
            esi = ESIClient(client)
            payload, e_tag = await esi.market_prices(curr_etag)

        pulled_at = datetime.now(UTC)
        ensure_schema(conn)
        
        if payload and e_tag:
            count = insert_prices(conn, payload, pulled_at, e_tag)
            print(f"Inserted {count} rows into {DB_PATH} at {pulled_at}")
        else:
            print("Prices Up to Date")
