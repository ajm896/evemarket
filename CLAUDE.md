# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Early-stage tool that pulls EVE Online market data from the ESI API (`https://esi.evetech.net`). It fetches `/markets/prices` and persists each pull as an append-only snapshot in a local DuckDB database (`evemarket.duckdb`), so `adjusted_price`/`average_price` accumulate into a queryable time series.

## Commands

Managed with `uv` (see `uv.lock`, `.python-version` pins 3.14).

```bash
uv sync                  # install/refresh the environment (installs the package itself)
uv run evemarket         # run the price pull via the console script
uv run -m evemarket      # same pull, via the package __main__
```

There is no test suite, linter, or formatter configured — don't invent commands for them.

## Architecture

`src` layout — the package is installed into the venv by `uv sync`, so imports are absolute (`from evemarket.storage import make_connection`) and work from any working directory. Never add `sys.path` juggling or relative-to-cwd imports.

```
src/evemarket/
  __main__.py       # sync main() -> asyncio.run(pull_prices()); the [project.scripts] target
  esi/
    client.py       # ESIClient
    config.py       # BASE_URL, COMPATIBILITY_DATE, USER_AGENT, TIMEOUT, make_client()
  storage/
    config.py       # DB_PATH, make_connection(), ensure_schema()
    prices.py        # insert_prices()
  jobs/prices.py    # pull_prices()
```

- `esi/client.py` — thin async wrapper over an injected `httpx.AsyncClient`. It owns an `asyncio.Semaphore(30)` to cap concurrency against ESI's rate limits; every request method should acquire it. The client does *not* create or close the `AsyncClient` — it borrows one. Request methods call `response.raise_for_status()` and return the raw `response.content` bytes — there is no intermediate typed model. JSON parsing happens once, in DuckDB, at the storage layer.
- `esi/config.py` — `make_client()` builds the `AsyncClient` with the ESI base URL, timeout, and required headers. It returns an un-entered client; the caller owns its lifecycle.
- `storage/config.py` — `DB_PATH` (default `evemarket.duckdb` in the working directory, overridable via the `EVEMARKET_DB` env var), `make_connection()` (returns an un-entered `duckdb.DuckDBPyConnection`; the caller owns the lifecycle, matching `esi.config.make_client()`), and `ensure_schema()` (idempotent `CREATE TABLE IF NOT EXISTS`).
- `storage/prices.py` — `insert_prices(conn, payload: bytes, pulled_at)` wraps the raw JSON bytes in `io.BytesIO` and hands them to `conn.read_json(...)`, then does a single `INSERT INTO market_prices SELECT ... FROM prices`. DuckDB infers columns from the JSON keys directly — nothing is decoded into Python objects first. `market_prices` is append-only (no primary key/dedup); every pull adds a fresh batch of rows stamped with one shared `pulled_at`, so history accumulates as a time series.
- `jobs/` — one module per pull. Each drives `ESIClient` inside `async with make_client()`, then writes the result via `storage` inside `with make_connection() as conn:`.

Each package's `__init__.py` re-exports its public names (`from evemarket.esi import ESIClient`); import from the package, not the leaf module, outside the package itself.

New ESI endpoints belong as methods on `ESIClient` following the `market_prices` shape (semaphore → request → `raise_for_status()` → raw bytes). Persisting them belongs in `storage/`, following the same read_json-straight-into-a-table pattern rather than adding typed models.

## ESI request headers

ESI requires the headers set in `esi/config.py`; keep them on any new client:

- `User-Agent` — ESI policy requires a contact identifier. The current value is a placeholder (`aj@example.com`).
- `X-Compatibility-Date` — pins the ESI schema version (currently `2026-07-21`). Bumping it can change response shapes, so update the `ensure_schema()` DDL and the `conn.read_json` column expectations in `storage/` alongside it.

## Dependencies

- `duckdb` — parses ESI JSON directly (`conn.read_json`) and persists it.
- `fsspec` — required by DuckDB's `read_json` to accept file-like objects (e.g. `io.BytesIO`) instead of only path strings; without it `conn.read_json(io.BytesIO(...))` raises `InvalidInputException`.
- `pytz` — required to fetch `TIMESTAMPTZ` columns back through the Python API; without it, querying `market_prices` from Python raises `InvalidInputException`.
