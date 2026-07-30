import os
from pathlib import Path

import duckdb

DB_PATH = Path(os.environ.get("EVEMARKET_DB", "data/evemarket.duckdb"))


def make_connection(path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection to the local database file.

    The caller owns the returned connection and is responsible for entering
    and closing it, matching esi.config.make_client's ownership contract.
    """
    return duckdb.connect(path)


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_prices (
            pulled_at      TIMESTAMPTZ NOT NULL,
            etag           TEXT,
            type_id        INTEGER     NOT NULL,
            adjusted_price DOUBLE,
            average_price  DOUBLE
        )
        """
    )
