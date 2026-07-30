import base64
import hashlib
import json
import secrets
from typing import Any
from urllib.parse import quote, urlencode

from httpx import AsyncClient

from evemarket.sso.config import (
    AUTHORIZE_PATH,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPES,
    SSO_BASE_URL,
    TOKEN_PATH,
)


def _b64url(raw: bytes) -> str:
    """base64url with padding stripped, as PKCE and JWT both require."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def pkce_pair() -> tuple[str, str]:
    """A (code_verifier, code_challenge) pair for S256.

    32 random bytes, base64url-encoded unpadded, is the verifier; the challenge
    is base64url(SHA256(verifier *as ASCII text*)) — the hash is over the
    encoded string, not the original bytes.
    """
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def new_state() -> str:
    return secrets.token_urlsafe(16)


def authorize_url(code_challenge: str, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "scope": " ".join(SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        },
        quote_via=quote,
    )
    return f"{SSO_BASE_URL}{AUTHORIZE_PATH}?{query}"


async def exchange_code(client: AsyncClient, code: str, code_verifier: str) -> dict[str, Any]:
    """Trade an authorization code for tokens.

    The token endpoint accepts *only* form encoding — a JSON or query-string
    payload is rejected. Passing `data=` makes httpx set
    Content-Type: application/x-www-form-urlencoded.
    """
    response = await client.post(
        TOKEN_PATH,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
        },
    )
    _ = response.raise_for_status()
    return response.json()


async def refresh_tokens(client: AsyncClient, refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a fresh access token.

    The response's refresh_token may differ from the one sent — EVE rotates
    refresh tokens — so the caller must persist whatever comes back.
    """
    response = await client.post(
        TOKEN_PATH,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        },
    )
    _ = response.raise_for_status()
    return response.json()


def decode_claims(access_token: str) -> dict[str, Any]:
    """Read the claims out of an SSO access token *without verifying it*.

    No signature check and no JWKS fetch, therefore no crypto dependency. That
    is sound here and only here: this token is one we just received ourselves
    over TLS directly from login.eveonline.com, and we use the claims solely to
    label our own database row (which character is this, when does the token
    expire). We never accept a token from a third party, and we never make an
    authorisation decision from these claims — ESI itself verifies the
    signature on every request. If this project ever accepts a token it did not
    fetch, this function must be replaced with real verification against
    https://login.eveonline.com/oauth/jwks.
    """
    body = access_token.split(".")[1]
    padded = body + "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def claim_character_id(claims: dict[str, Any]) -> int:
    """`sub` is "CHARACTER:EVE:123123"."""
    return int(str(claims["sub"]).rsplit(":", 1)[1])


def claim_scopes(claims: dict[str, Any]) -> str:
    """`scp` is a list of scopes — except with exactly one scope, where CCP
    sends a bare string. Normalise both to the space-delimited form."""
    scp = claims["scp"]
    return scp if isinstance(scp, str) else " ".join(scp)
