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
    conn.execute("ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS etag TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sso_tokens (
            character_id      BIGINT      PRIMARY KEY,
            character_name    TEXT        NOT NULL,
            refresh_token     TEXT        NOT NULL,
            access_token      TEXT,
            access_expires_at TIMESTAMPTZ,
            scopes            TEXT        NOT NULL,
            updated_at        TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS character_assets (
            pulled_at         TIMESTAMPTZ NOT NULL,
            character_id      BIGINT      NOT NULL,
            item_id           BIGINT      NOT NULL,
            type_id           INTEGER     NOT NULL,
            quantity          BIGINT,
            location_id       BIGINT,
            location_flag     TEXT,
            location_type     TEXT,
            is_singleton      BOOLEAN,
            is_blueprint_copy BOOLEAN
        )
        """
    )
