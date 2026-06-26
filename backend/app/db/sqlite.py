import sqlite3
from collections.abc import Iterable
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


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
