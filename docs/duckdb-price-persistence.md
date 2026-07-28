# Persist `/markets/prices` pulls to DuckDB

## Context

`evemarket` currently fetches ESI's `/markets/prices` and prints the structs to
stdout (`jobs/prices.py`). Every pull is discarded. `duckdb>=1.5.5` has been a
declared dependency since the initial commit but is never imported, and
`CLAUDE.md` names persistence as the obvious next layer.

`/markets/prices` is a full-catalog snapshot of `adjusted_price` /
`average_price` that ESI refreshes roughly hourly. Those two numbers are only
interesting *as a time series* — comparing today's adjusted price against last
week's is the whole point. So the store is **append-only**: each pull writes a
fresh set of rows stamped with when it was taken, and history accumulates.

A second, smaller problem gets fixed on the way: `ESIClient.market_prices`
(`src/evemarket/esi/client.py:16`) hands `response.content` to
`msgspec.json.decode` without checking the status code. When ESI returns a 420
(rate limited) or 5xx, the body is an error object, and the failure surfaces as
a confusing msgspec decode error. Once pulls are being *written*, that check
matters more — a bad response must abort the pull, not land in the table.

Outcome: `uv run evemarket` becomes a job worth running on a schedule, and the
data it collects is queryable with DuckDB.

## Approach

### 1. New `storage/` package

Mirrors the existing `esi/` split — a config/factory module that builds a
resource and hands ownership to the caller, plus a module that does the work.

**`src/evemarket/storage/database.py`**

- `DB_PATH` — default database path, overridable via the `EVEMARKET_DB`
  environment variable, defaulting to `evemarket.duckdb` in the working
  directory.
- `make_connection(path: Path = DB_PATH) -> duckdb.DuckDBPyConnection` —
  returns an **un-entered** connection, exactly like
  `esi/config.py:make_client()` returns an un-entered `AsyncClient`. The caller
  owns the lifecycle (`with make_connection() as conn:`);
  `DuckDBPyConnection` supports the context-manager protocol and closes on
  exit. Docstring should state the ownership contract, matching `make_client`.
- `ensure_schema(conn)` — idempotent `CREATE TABLE IF NOT EXISTS`, called by
  each job before writing. No migration framework; the project is one table old.

**`src/evemarket/storage/prices.py`**

- The `market_prices` DDL, append-only:

  ```sql
  CREATE TABLE IF NOT EXISTS market_prices (
      pulled_at      TIMESTAMPTZ NOT NULL,
      type_id        INTEGER     NOT NULL,
      adjusted_price DOUBLE,
      average_price  DOUBLE
  )
  ```

  No primary key or uniqueness constraint — two pulls within the same ESI cache
  window legitimately produce identical rows under different `pulled_at`
  values, and deduplicating is a query-time concern.
- `insert_prices(conn, prices: list[Price], pulled_at: datetime) -> int` —
  builds explicit tuples (`(pulled_at, p.type_id, p.adjusted_price,
  p.average_price)`, not `msgspec.structs.astuple`, so the column mapping stays
  readable and survives struct field reordering) and writes them with a single
  `conn.executemany("INSERT INTO market_prices VALUES (?, ?, ?, ?)", rows)`.
  Returns the row count for the job to report. ~15k rows per pull — one
  `executemany` is plenty; no need for Arrow/pandas, and neither is a dependency.

**`src/evemarket/storage/__init__.py`** — re-export `make_connection`,
`ensure_schema`, `insert_prices` in `__all__`, per the repo's
import-from-the-package convention.

### 2. Status check in the ESI client

`src/evemarket/esi/client.py` — call `response.raise_for_status()` inside the
`async with self._semaphore` block, before decoding, so an ESI error raises
`httpx.HTTPStatusError` and aborts the pull instead of producing a decode error
or a partial write. Every future request method follows the same shape
(semaphore → request → raise_for_status → typed decode); worth a line in
CLAUDE.md's "New ESI endpoints belong as methods on ESIClient" note.

### 3. Rewire the job

`src/evemarket/jobs/prices.py` — `pull_prices()` keeps driving `ESIClient`
inside `async with make_client()`, then:

- stamps one `pulled_at = datetime.now(UTC)` for the whole batch (a snapshot is
  a single point in time, so all rows share it),
- opens `with make_connection() as conn:`, calls `ensure_schema(conn)`, then
  `insert_prices(...)`,
- replaces the per-row `print(p)` loop with a single summary line — row count,
  `pulled_at`, and the database path — so the console script still reports
  something useful without dumping 15k lines.

The DuckDB write is synchronous inside an async function. That is fine and
deliberate: it is one bulk insert at the end of the job with nothing else in
flight. Don't reach for a thread executor.

### 4. Housekeeping

- `.gitignore` — add `*.duckdb` (and `*.duckdb.wal`) so local databases stay
  out of git.
- `CLAUDE.md` — extend the architecture tree with `storage/`, describe the
  append-only convention and the `make_connection` ownership contract
  alongside the existing `make_client` note, and record `EVEMARKET_DB`.
  (PR #1 set the precedent of updating CLAUDE.md in the same change.)

## Critical files

| File | Change |
| --- | --- |
| `src/evemarket/storage/database.py` | new — `DB_PATH`, `make_connection`, `ensure_schema` |
| `src/evemarket/storage/prices.py` | new — DDL + `insert_prices` |
| `src/evemarket/storage/__init__.py` | new — re-exports |
| `src/evemarket/esi/client.py` | add `raise_for_status()` |
| `src/evemarket/jobs/prices.py` | write to DuckDB instead of printing |
| `.gitignore`, `CLAUDE.md` | housekeeping |

## Verification

A live pull against ESI was confirmed working before implementation started:
`/markets/prices` returned **15,833** entries that decoded cleanly into
`list[Price]`. Two facts from that run shape the storage layer — `average_price`
was null for 2,032 of the 15,833 entries, so the column must be nullable, while
`adjusted_price` was never null in practice (keep it optional anyway, since ESI
documents it as omittable). Tritanium (`type_id` 34) came back at 2.94 adjusted
/ 3.69 average.

*Storage layer, no network needed* — exercise it against a hand-built
`list[Price]`:

1. `uv sync`
2. Run a throwaway script (in a scratchpad, not committed) that constructs a few
   `Price` structs — including one with `average_price=None` — opens
   `make_connection(Path(tmp))`, calls `ensure_schema` + `insert_prices`, then
   runs a **second** time with a later `pulled_at`.
3. Query back: `SELECT pulled_at, count(*) FROM market_prices GROUP BY 1` —
   expect two distinct `pulled_at` groups, confirming rows accumulate rather
   than overwrite, and that the `None` round-trips as SQL `NULL`.
4. Re-open the same file to confirm `ensure_schema` is genuinely idempotent and
   the data survives reconnection.

*End to end:*

5. `uv run evemarket` — expect a summary line reporting ~15.8k rows, not a wall
   of structs.
6. Run it twice a few minutes apart, then
   `SELECT type_id, pulled_at, average_price FROM market_prices WHERE type_id =
   34 ORDER BY pulled_at` to see the beginnings of a series.
7. Confirm the error path: point `BASE_URL` at a URL that 404s and check the job
   raises `httpx.HTTPStatusError` and writes nothing.

No test suite, linter, or formatter is configured in this repo, and per
CLAUDE.md this plan does not invent commands for them.

## Deliberately out of scope

- **`/markets/{region_id}/orders`** — the actual order book, paginated via
  `X-Pages`, and the first thing that justifies the `Semaphore(30)` already
  sitting unused in `ESIClient`. Natural next slice once there's somewhere to
  put it.
- **Capturing ESI's `Last-Modified` / `Expires` headers** so repeated pulls
  inside one cache window can be recognised as the same snapshot instead of
  stored twice. Cheap and genuinely useful, but it changes
  `market_prices()`'s return signature, so it belongs in its own change.
- Retries/backoff, name resolution via `/universe/types`, tests, and the empty
  README.
