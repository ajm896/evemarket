"""EVE SSO (OAuth2 + PKCE) login and token refresh."""

from evemarket.sso.callback import make_callback_server, wait_for_callback
from evemarket.sso.config import SCOPES, make_sso_client
from evemarket.sso.oauth import (
    authorize_url,
    claim_character_id,
    claim_scopes,
    decode_claims,
    exchange_code,
    new_state,
    pkce_pair,
    refresh_tokens,
)
from evemarket.sso.tokens import access_token

__all__ = [
    "SCOPES",
    "make_sso_client",
    "authorize_url",
    "new_state",
    "pkce_pair",
    "exchange_code",
    "refresh_tokens",
    "decode_claims",
    "claim_character_id",
    "claim_scopes",
    "access_token",
    "make_callback_server",
    "wait_for_callback",
]
