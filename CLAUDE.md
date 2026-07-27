# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Early-stage tool that pulls EVE Online market data from the ESI API (`https://esi.evetech.net`). Currently it fetches `/markets/prices` and prints the results; `duckdb` is a declared dependency but not yet wired in, so persistence is the obvious next layer.

## Commands

Managed with `uv` (see `uv.lock`, `.python-version` pins 3.14).

```bash
uv sync                  # install/refresh the environment
uv run main.py           # run the price pull
uv run pull_prices.py    # same pull, via the module's own __main__ guard
```

There is no test suite, linter, or formatter configured — don't invent commands for them.

## Architecture

Three layers, each in a single top-level module:

- `models/price.py` — `msgspec.Struct` types. Decoding is done with `msgspec.json.decode(..., type=...)` directly against `response.content` (never `response.json()`), so struct fields must match ESI's JSON field names exactly. Fields that ESI omits per-item are `| None = None`.
- `ESIClient.py` — thin async wrapper over an injected `httpx.AsyncClient`. It owns an `asyncio.Semaphore(30)` to cap concurrency against ESI's rate limits; every request method should acquire it. The client does *not* create or close the `AsyncClient` — it borrows one.
- `pull_prices.py` — the composition root: builds the `AsyncClient` with the ESI base URL, timeout, and required headers, then drives `ESIClient` inside `async with`. `main.py` is just an `asyncio.run` entry point around it.

New ESI endpoints belong as methods on `ESIClient` following the `market_prices` shape (semaphore → request → typed decode), with a matching struct in `models/`.

## ESI request headers

ESI requires the headers set in `pull_prices.py`; keep them on any new client:

- `User-Agent` — ESI policy requires a contact identifier. The current value is a placeholder (`aj@example.com`).
- `X-Compatibility-Date` — pins the ESI schema version (currently `2026-07-21`). Bumping it can change response shapes, so update the structs in `models/` alongside it.
