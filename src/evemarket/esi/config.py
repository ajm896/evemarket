from httpx import AsyncClient

BASE_URL = "https://esi.evetech.net"
# Pins the ESI schema version. Bumping this can change response shapes, so update
# ensure_schema()'s DDL and the storage/ read_json column expectations alongside it.
COMPATIBILITY_DATE = "2026-07-21"
# ESI policy requires a contact identifier.
USER_AGENT = "EveMarketData/0.1 (AJ; amorris@amorris.cc)"
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
