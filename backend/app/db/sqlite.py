import sqlite3
from collections.abc import Iterable
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
ACCOUNT_TABLES = ("sync_jobs", "spaces", "nodes", "documents", "blocks", "chunks")
DEFAULT_ACCOUNT_ID = "default"


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(sqlite_path: Path) -> sqlite3.Connection:
    ensure_parent_dir(sqlite_path)
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(sqlite_path: Path) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(sqlite_path) as connection:
        _migrate_account_id_schema(connection, schema_sql)
        connection.executescript(schema_sql)


def list_tables(sqlite_path: Path) -> Iterable[str]:
    with connect(sqlite_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]


def ping(sqlite_path: Path) -> None:
    with connect(sqlite_path) as connection:
        connection.execute("SELECT 1").fetchone()


def _migrate_account_id_schema(connection: sqlite3.Connection, schema_sql: str) -> None:
    legacy_tables = [
        table
        for table in ACCOUNT_TABLES
        if _table_exists(connection, table)
        and "account_id" not in _table_columns(connection, table)
    ]
    if not legacy_tables:
        return

    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        _drop_known_indexes(connection)
        for table in legacy_tables:
            connection.execute(f"ALTER TABLE {table} RENAME TO {table}__legacy_account")
        connection.executescript(schema_sql)
        _copy_legacy_rows(connection, legacy_tables)
        for table in reversed(legacy_tables):
            connection.execute(f"DROP TABLE IF EXISTS {table}__legacy_account")
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def _drop_known_indexes(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'index'
          AND tbl_name IN (
              'sync_jobs', 'spaces', 'nodes', 'documents', 'blocks', 'chunks'
          )
        """
    ).fetchall()
    for row in rows:
        name = row["name"]
        if not name.startswith("sqlite_autoindex_"):
            connection.execute(f"DROP INDEX IF EXISTS {name}")


def _copy_legacy_rows(connection: sqlite3.Connection, legacy_tables: list[str]) -> None:
    if "sync_jobs" in legacy_tables:
        connection.execute(
            """
            INSERT INTO sync_jobs (
                job_id, account_id, scope_type, scope_id, status, total_items,
                processed_items, failed_items, error_message, created_at, started_at, finished_at
            )
            SELECT job_id, ?, scope_type, scope_id, status, total_items,
                   processed_items, failed_items, error_message, created_at, started_at, finished_at
            FROM sync_jobs__legacy_account
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    if "spaces" in legacy_tables:
        connection.execute(
            """
            INSERT INTO spaces (account_id, space_id, name, description, updated_time, synced_at)
            SELECT ?, space_id, name, description, updated_time, synced_at
            FROM spaces__legacy_account
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    if "nodes" in legacy_tables:
        connection.execute(
            """
            INSERT INTO nodes (
                account_id, node_token, space_id, parent_node_token, obj_token, obj_type,
                title, source_url, updated_time, deleted_at, synced_at
            )
            SELECT ?, node_token, space_id, parent_node_token, obj_token, obj_type,
                   title, source_url, updated_time, deleted_at, synced_at
            FROM nodes__legacy_account
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    if "documents" in legacy_tables:
        connection.execute(
            """
            INSERT INTO documents (
                account_id, doc_token, space_id, node_token, doc_type, title, source_url,
                updated_time, block_hash, deleted_at, synced_at
            )
            SELECT ?, doc_token, space_id, node_token, doc_type, title, source_url,
                   updated_time, block_hash, deleted_at, synced_at
            FROM documents__legacy_account
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    if "blocks" in legacy_tables:
        connection.execute(
            """
            INSERT INTO blocks (
                account_id, block_id, doc_token, parent_block_id, block_type, heading_level,
                text, raw_json, content_hash, updated_at
            )
            SELECT ?, block_id, doc_token, parent_block_id, block_type, heading_level,
                   text, raw_json, content_hash, updated_at
            FROM blocks__legacy_account
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    if "chunks" in legacy_tables:
        connection.execute(
            """
            INSERT INTO chunks (
                account_id, chunk_id, space_id, node_token, doc_token, doc_type, title,
                section_path, source_url, block_ids, content, content_hash, updated_time,
                indexed_at, deleted_at
            )
            SELECT ?, chunk_id, space_id, node_token, doc_token, doc_type, title,
                   section_path, source_url, block_ids, content, content_hash, updated_time,
                   indexed_at, deleted_at
            FROM chunks__legacy_account
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
