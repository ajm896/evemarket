import asyncio
from datetime import UTC, datetime

from evemarket.esi import ESIClient
from evemarket.esi.config import make_client
from evemarket.sso import access_token, make_sso_client
from evemarket.storage import DB_PATH, ensure_schema, insert_assets, make_connection


async def pull_assets(character_id: int | None = None) -> None:
    async with make_sso_client() as sso:
        character_id, token = await access_token(sso, character_id)

    async with make_client() as client:
        esi = ESIClient(client)
        first, pages = await esi.character_assets(character_id, token)
        rest = await asyncio.gather(
            *(esi.character_assets(character_id, token, page) for page in range(2, pages + 1))
        )
    payloads = [first, *(payload for payload, _ in rest)]

    pulled_at = datetime.now(UTC)
    with make_connection() as conn:
        ensure_schema(conn)
        count = insert_assets(conn, payloads, pulled_at, character_id)
    print(f"Inserted {count} asset rows for character {character_id} into {DB_PATH} at {pulled_at}")
