from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from evemarket.sso.config import REFRESH_MARGIN
from evemarket.sso.oauth import claim_character_id, claim_scopes, decode_claims, refresh_tokens
from evemarket.storage import ensure_schema, load_token, make_connection, save_token


async def access_token(client: AsyncClient, character_id: int | None = None) -> tuple[int, str]:
    """A (character_id, access_token) pair valid right now.

    Reuses the stored access token while it has more than REFRESH_MARGIN
    seconds left; otherwise refreshes and persists the result. EVE rotates
    refresh tokens, so the token that comes back must be written down or the
    next run is locked out.

    The database is opened and closed *before* the refresh request and reopened
    *after* it — no DuckDB connection is ever held across an await.
    """
    with make_connection() as conn:
        ensure_schema(conn)
        row = load_token(conn, character_id)

    if row is None:
        raise RuntimeError("No character authorised. Run: evemarket login")

    character_id, refresh_token, stored_access, expires_at = row
    now = datetime.now(UTC)
    if stored_access and expires_at and expires_at - now > timedelta(seconds=REFRESH_MARGIN):
        return character_id, stored_access

    payload = await refresh_tokens(client, refresh_token)
    claims = decode_claims(payload["access_token"])
    expires_at = now + timedelta(seconds=payload["expires_in"])

    with make_connection() as conn:
        save_token(
            conn,
            character_id=claim_character_id(claims),
            character_name=claims["name"],
            refresh_token=payload["refresh_token"],
            access_token=payload["access_token"],
            access_expires_at=expires_at,
            scopes=claim_scopes(claims),
        )

    return character_id, payload["access_token"]
