import os

from httpx import AsyncClient

from evemarket.esi.config import USER_AGENT

SSO_BASE_URL = "https://login.eveonline.com"
AUTHORIZE_PATH = "/v2/oauth/authorize"
TOKEN_PATH = "/v2/oauth/token"

# Not a secret: PKCE replaces the client secret for a public/native app.
CLIENT_ID = os.environ.get("EVEMARKET_CLIENT_ID", "")
REDIRECT_URI = os.environ.get("EVEMARKET_CALLBACK", "http://localhost:8923/callback")
SCOPES = ("esi-assets.read_assets.v1",)

TIMEOUT = 30
# Seconds of slack before a stored access token is treated as expired.
REFRESH_MARGIN = 60
# Seconds to wait for the browser to redirect back to the loopback server.
CALLBACK_TIMEOUT = 300


def make_sso_client() -> AsyncClient:
    """An httpx.AsyncClient for login.eveonline.com.

    Deliberately not esi.config.make_client(): the SSO host is a different
    origin, and X-Compatibility-Date / Accept-Language are ESI-only headers
    that mean nothing to the identity provider.

    The caller owns the returned client and is responsible for entering and
    closing it, matching esi.config.make_client's ownership contract.
    """
    return AsyncClient(
        base_url=SSO_BASE_URL,
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
