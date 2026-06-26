from pathlib import Path

from backend.app.db.sqlite import initialize_database, list_tables


def test_initialize_database_creates_core_tables(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "state" / "test.sqlite3"

    initialize_database(sqlite_path)

    tables = set(list_tables(sqlite_path))
    assert {
        "sync_jobs",
        "spaces",
        "nodes",
        "documents",
        "blocks",
        "chunks",
        "index_events",
        "settings",
    }.issubset(tables)
