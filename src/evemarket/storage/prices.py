import io
from datetime import datetime

import duckdb


def insert_prices(conn: duckdb.DuckDBPyConnection, payload: bytes, pulled_at: datetime) -> int:
    """Insert a /markets/prices JSON payload straight into market_prices.

    DuckDB parses and types the JSON itself; the payload never passes through
    a Python object per-row.
    """
    prices = conn.read_json(io.BytesIO(payload))
    count: int = conn.sql("SELECT count(*) FROM prices").fetchone()[0]
    conn.execute(
        "INSERT INTO market_prices SELECT ?, type_id, adjusted_price, average_price FROM prices",
        [pulled_at],
    )
    return count
