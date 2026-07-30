# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Early-stage tool that pulls EVE Online market data and, for an SSO-authorised character, asset data from the ESI API (`https://esi.evetech.net`). It fetches `/markets/prices` and `/characters/{id}/assets`, persisting each pull as an append-only snapshot in a local DuckDB database (`data/evemarket.duckdb`), so `adjusted_price`/`average_price` and asset holdings accumulate into a queryable time series.

## Commands

Managed with `uv` (see `uv.lock`, `.python-version` pins 3.14).

```bash
uv sync                  # install/refresh the environment (installs the package itself)
uv run evemarket         # prints subcommand help
uv run evemarket login   # authorise a character via EVE SSO (opens a browser)
uv run evemarket prices  # pull /markets/prices into DuckDB
uv run evemarket assets  # pull the most-recently-authorised character's assets into DuckDB
uv run -m evemarket <subcommand>  # same subcommands, via the package __main__
```

Authenticated pulls (`login`, `assets`) require `EVEMARKET_CLIENT_ID` — see "EVE SSO" below.

There is no test suite, linter, or formatter configured — don't invent commands for them.

## Architecture

`src` layout — the package is installed into the venv by `uv sync`, so imports are absolute (`from evemarket.storage import make_connection`) and work from any working directory. Never add `sys.path` juggling or relative-to-cwd imports.

```
src/evemarket/
  __main__.py       # sync main() -> argparse dispatch -> asyncio.run(...); the [project.scripts] target
  esi/
    client.py       # ESIClient
    config.py       # BASE_URL, COMPATIBILITY_DATE, USER_AGENT, TIMEOUT, make_client()
  sso/
    config.py       # SSO_BASE_URL, CLIENT_ID, REDIRECT_URI, SCOPES, make_sso_client()
    oauth.py        # PKCE, authorize URL, token exchange/refresh, unverified JWT claim decode
    callback.py     # one-shot loopback HTTP server for the SSO redirect
    tokens.py       # access_token() — DB-cached, refreshes and persists as needed
  storage/
    config.py       # DB_PATH, make_connection(), ensure_schema()
    prices.py       # insert_prices()
    assets.py       # ASSET_COLUMNS, insert_assets()
    tokens.py       # load_token(), save_token()
  jobs/
    prices.py       # pull_prices()
    assets.py       # pull_assets()
    login.py        # login()
```

- `esi/client.py` — thin async wrapper over an injected `httpx.AsyncClient`. It owns an `asyncio.Semaphore(30)` to cap concurrency against ESI's rate limits; every request method should acquire it. The client does *not* create or close the `AsyncClient` — it borrows one. Request methods call `response.raise_for_status()` and return the raw `response.content` bytes — there is no intermediate typed model. JSON parsing happens once, in DuckDB, at the storage layer.
- `esi/config.py` — `make_client()` builds the `AsyncClient` with the ESI base URL, timeout, and required headers. It returns an un-entered client; the caller owns its lifecycle.
- `sso/` — EVE SSO (OAuth2 authorization-code + PKCE) against `login.eveonline.com`, a **different origin** from ESI. `sso/config.py:make_sso_client()` deliberately does *not* reuse `esi.config.make_client()`: it must not send `X-Compatibility-Date` or `Accept-Language`, which are ESI-only headers meaningless to the identity provider. `sso/oauth.py:decode_claims()` reads the access token's JWT payload with a plain base64url decode and **no signature verification** — sound only because the token is one we just received ourselves over TLS directly from `login.eveonline.com` and never accept from a third party; if that ever changes, replace it with real verification against `https://login.eveonline.com/oauth/jwks`. `sso/tokens.py:access_token()` is the provider every authenticated job calls: it reads the stored token, reuses it if it has more than `REFRESH_MARGIN` seconds left, otherwise refreshes and persists the (possibly rotated — EVE rotates refresh tokens) result.
- `storage/config.py` — `DB_PATH` (default `data/evemarket.duckdb`, overridable via the `EVEMARKET_DB` env var), `make_connection()` (returns an un-entered `duckdb.DuckDBPyConnection`; the caller owns the lifecycle, matching `esi.config.make_client()`), and `ensure_schema()` (idempotent `CREATE TABLE IF NOT EXISTS` for every table in the project — jobs don't track which tables they touch, they just call `ensure_schema()`).
- `storage/prices.py`, `storage/assets.py` — `insert_prices`/`insert_assets` wrap raw JSON bytes in `io.BytesIO` and hand them to `conn.read_json(...)`, then do a single `INSERT INTO ... SELECT ... FROM <relation>`. DuckDB infers (or, for `insert_assets`, is given an explicit `columns=` dict for) the columns directly from JSON — nothing is decoded into Python objects first. Both tables are append-only (no primary key/dedup); every pull adds a fresh batch of rows stamped with one shared `pulled_at`, so history accumulates as a time series. `insert_assets` takes a **list** of page payloads so a multi-page asset pull lands as one snapshot in one `INSERT`.
- `storage/tokens.py` — the one exception to append-only. `sso_tokens` holds *state* (the current refresh/access token per character), not an observation, so `save_token` upserts on `PRIMARY KEY (character_id)` via `INSERT ... ON CONFLICT DO UPDATE` rather than accumulating rows.
- `jobs/` — one module per pull/action. Each drives `ESIClient` (and, for authenticated pulls, `sso.access_token()`) inside `async with make_client()` / `async with make_sso_client()`, then writes the result via `storage` inside `with make_connection() as conn:`. **Never hold a DuckDB connection open across an `await`** — every job opens a connection, does its DB work, closes it, then does HTTP, then reopens a connection to write.

Each package's `__init__.py` re-exports its public names (`from evemarket.esi import ESIClient`); import from the package, not the leaf module, outside the package itself.

New ESI endpoints belong as methods on `ESIClient` following the `market_prices`/`character_assets` shape (semaphore → request → `raise_for_status()` → raw bytes). Persisting them belongs in `storage/`, following the same read_json-straight-into-a-table pattern rather than adding typed models.

## ESI request headers

ESI requires the headers set in `esi/config.py`; keep them on any new ESI client (but *not* on the SSO client — see `sso/` above):

- `User-Agent` — ESI policy requires a contact identifier.
- `X-Compatibility-Date` — pins the ESI schema version (currently `2026-07-21`). Bumping it can change response shapes, so update the `ensure_schema()` DDL and the `conn.read_json` column expectations in `storage/` alongside it.

## EVE SSO

Authenticated endpoints (currently: character assets, scope `esi-assets.read_assets.v1`) require a one-time app registration at developers.eveonline.com (Connection Type "Authentication & API Access", callback URL exactly `http://localhost:8923/callback`), then `export EVEMARKET_CLIENT_ID=<Client ID>`. `CLIENT_ID` is not a secret — PKCE replaces the client secret for this public/native-app flow, and no client secret is ever read or stored. `EVEMARKET_CALLBACK` overrides the default loopback URL if port 8923 is taken; changing it means updating the CCP registration too. `uv run evemarket login` opens a browser, runs a one-shot local server to catch the redirect, and stores the resulting refresh token in `sso_tokens`. Authenticated jobs (`pull_assets`) call `sso.access_token()`, which refreshes automatically.

## Dependencies

- `duckdb` — parses ESI JSON directly (`conn.read_json`) and persists it.
- `fsspec` — required by DuckDB's `read_json` to accept file-like objects (e.g. `io.BytesIO`) instead of only path strings; without it `conn.read_json(io.BytesIO(...))` raises `InvalidInputException`.
- `pytz` — required to fetch `TIMESTAMPTZ` columns back through the Python API; without it, querying `market_prices` from Python raises `InvalidInputException`.
