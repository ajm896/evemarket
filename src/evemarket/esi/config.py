from httpx import AsyncClient

BASE_URL = "https://esi.evetech.net"
# Pins the ESI schema version. Bumping this can change response shapes, so update
# the structs in evemarket.models alongside it.
COMPATIBILITY_DATE = "2026-07-21"
# ESI policy requires a contact identifier. This is still a placeholder.
USER_AGENT = "EveMarketData/0.1 (AJ; aj@example.com)"
TIMEOUT = 30


def make_client() -> AsyncClient:
    """An httpx.AsyncClient preconfigured with ESI's required headers.

    The caller owns the returned client and is responsible for entering and
    closing it; ESIClient only borrows it.
    """
    return AsyncClient(
        base_url=BASE_URL,
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "X-Compatibility-Date": COMPATIBILITY_DATE,
            "Accept-Language": "en",
        },
    )
