import io
from datetime import datetime

import duckdb

# Pinned explicitly rather than inferred: is_blueprint_copy is absent from most
# rows (and from every row for a character with no blueprint copies, in which
# case inference drops the column entirely), and inference otherwise reorders
# columns by first-seen JSON key and widens type_id to BIGINT. Keep this in
# sync with ensure_schema()'s character_assets DDL and with the ESI response
# shape pinned by esi.config.COMPATIBILITY_DATE.
ASSET_COLUMNS = {
    "item_id": "BIGINT",
    "type_id": "INTEGER",
    "quantity": "BIGINT",
    "location_id": "BIGINT",
    "location_flag": "TEXT",
    "location_type": "TEXT",
    "is_singleton": "BOOLEAN",
    "is_blueprint_copy": "BOOLEAN",
}


def insert_assets(
    conn: duckdb.DuckDBPyConnection, payloads: list[bytes], pulled_at: datetime, character_id: int
) -> int:
    """Insert every page of a /characters/{id}/assets pull as one snapshot.

    read_json takes the whole list of page buffers at once, so all pages land
    in a single relation and a single INSERT — one snapshot, one pulled_at.
    The `assets` local name is load-bearing: DuckDB's replacement scan resolves
    it as a table name in the SQL below.
    """
    assets = conn.read_json([io.BytesIO(payload) for payload in payloads], columns=ASSET_COLUMNS)
    count: int = conn.sql("SELECT count(*) FROM assets").fetchone()[0]
    conn.execute(
        "INSERT INTO character_assets "
        "SELECT ?, ?, item_id, type_id, quantity, location_id, location_flag, "
        "location_type, is_singleton, is_blueprint_copy FROM assets",
        [pulled_at, character_id],
    )
    return count
