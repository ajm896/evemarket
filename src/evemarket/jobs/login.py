import webbrowser
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from typing import Any

from evemarket.sso import (
    authorize_url,
    claim_character_id,
    claim_scopes,
    decode_claims,
    exchange_code,
    make_callback_server,
    make_sso_client,
    new_state,
    pkce_pair,
    wait_for_callback,
)
from evemarket.sso.config import CLIENT_ID
from evemarket.storage import DB_PATH, ensure_schema, make_connection, save_token


async def login() -> None:
    if not CLIENT_ID:
        raise RuntimeError(
            "Set EVEMARKET_CLIENT_ID to your application's Client ID from "
            "https://developers.eveonline.com."
        )

    verifier, challenge = pkce_pair()
    state = new_state()
    url = authorize_url(challenge, state)

    captured: dict[str, Any] = {}
    with make_callback_server(captured, state) as server:
        print(f"Opening browser for EVE SSO login. If it doesn't open, visit:\n{url}")
        _ = webbrowser.open(url)
        code = await to_thread(wait_for_callback, server, captured)

    async with make_sso_client() as client:
        tokens = await exchange_code(client, code, verifier)

    claims = decode_claims(tokens["access_token"])
    character_id = claim_character_id(claims)
    character_name = claims["name"]
    scopes = claim_scopes(claims)
    expires_at = datetime.now(UTC) + timedelta(seconds=tokens["expires_in"])

    with make_connection() as conn:
        ensure_schema(conn)
        save_token(
            conn,
            character_id=character_id,
            character_name=character_name,
            refresh_token=tokens["refresh_token"],
            access_token=tokens["access_token"],
            access_expires_at=expires_at,
            scopes=scopes,
        )

    print(f"Authorised {character_name} ({character_id}) for [{scopes}]; token stored in {DB_PATH}")
