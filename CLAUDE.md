# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Early-stage tool that pulls EVE Online market data from the ESI API (`https://esi.evetech.net`). Currently it fetches `/markets/prices` and prints the results; `duckdb` is a declared dependency but not yet wired in, so persistence is the obvious next layer.

## Commands

Managed with `uv` (see `uv.lock`, `.python-version` pins 3.14).

```bash
uv sync                  # install/refresh the environment (installs the package itself)
uv run evemarket         # run the price pull via the console script
uv run -m evemarket      # same pull, via the package __main__
```

There is no test suite, linter, or formatter configured — don't invent commands for them.

## Architecture

`src` layout — the package is installed into the venv by `uv sync`, so imports are absolute (`from evemarket.models import Price`) and work from any working directory. Never add `sys.path` juggling or relative-to-cwd imports.

```
src/evemarket/
  __main__.py       # sync main() -> asyncio.run(pull_prices()); the [project.scripts] target
  esi/
    client.py       # ESIClient
    config.py       # BASE_URL, COMPATIBILITY_DATE, USER_AGENT, TIMEOUT, make_client()
  models/price.py   # msgspec structs
  jobs/prices.py    # pull_prices()
```

- `models/` — `msgspec.Struct` types. Decoding is done with `msgspec.json.decode(..., type=...)` directly against `response.content` (never `response.json()`), so struct fields must match ESI's JSON field names exactly. Fields that ESI omits per-item are `| None = None`.
- `esi/client.py` — thin async wrapper over an injected `httpx.AsyncClient`. It owns an `asyncio.Semaphore(30)` to cap concurrency against ESI's rate limits; every request method should acquire it. The client does *not* create or close the `AsyncClient` — it borrows one.
- `esi/config.py` — `make_client()` builds the `AsyncClient` with the ESI base URL, timeout, and required headers. It returns an un-entered client; the caller owns its lifecycle.
- `jobs/` — one module per pull. Each drives `ESIClient` inside `async with make_client()`.

Each package's `__init__.py` re-exports its public names (`from evemarket.esi import ESIClient`); import from the package, not the leaf module, outside the package itself.

New ESI endpoints belong as methods on `ESIClient` following the `market_prices` shape (semaphore → request → typed decode), with a matching struct in `models/` re-exported from `models/__init__.py`.

## ESI request headers

ESI requires the headers set in `esi/config.py`; keep them on any new client:

- `User-Agent` — ESI policy requires a contact identifier. The current value is a placeholder (`aj@example.com`).
- `X-Compatibility-Date` — pins the ESI schema version (currently `2026-07-21`). Bumping it can change response shapes, so update the structs in `evemarket/models/` alongside it.
