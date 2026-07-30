from datetime import UTC, datetime

import duckdb


def load_token(
    conn: duckdb.DuckDBPyConnection, character_id: int | None = None
) -> tuple[int, str, str | None, datetime | None] | None:
    """The stored (character_id, refresh_token, access_token, access_expires_at).

    With no character_id, returns the most recently authorised character —
    the same "newest row wins" idiom pull_prices uses to find the last etag.
    Returns None when nothing has been authorised yet.
    """
    if character_id is None:
        row = conn.sql(
            "SELECT character_id, refresh_token, access_token, access_expires_at "
            "FROM sso_tokens ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    else:
        row = conn.sql(
            "SELECT character_id, refresh_token, access_token, access_expires_at "
            "FROM sso_tokens WHERE character_id = ?",
            params=[character_id],
        ).fetchone()
    return row


def save_token(
    conn: duckdb.DuckDBPyConnection,
    character_id: int,
    character_name: str,
    refresh_token: str,
    access_token: str,
    access_expires_at: datetime,
    scopes: str,
) -> None:
    """Upsert the single current token row for a character."""
    conn.execute(
        """
        INSERT INTO sso_tokens VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (character_id) DO UPDATE SET
            character_name    = excluded.character_name,
            refresh_token     = excluded.refresh_token,
            access_token      = excluded.access_token,
            access_expires_at = excluded.access_expires_at,
            scopes            = excluded.scopes,
            updated_at        = excluded.updated_at
        """,
        [
            character_id,
            character_name,
            refresh_token,
            access_token,
            access_expires_at,
            scopes,
            datetime.now(UTC),
        ],
    )
