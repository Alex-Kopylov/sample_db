"""Tests for sample_db.db."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from sample_db import db


def _read_table_names(connection: sqlite3.Connection) -> set[str]:
    cursor = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
    )
    return {row[0] for row in cursor.fetchall()}


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    cursor = connection.execute(f"SELECT COUNT(*) FROM {table_name};")
    row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def _insert_customer(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO customers (id, name, email, country, created_at) "
        "VALUES (999999, 'Readonly User', 'readonly@example.com', 'US', '2026-01-01');"
    )
    connection.commit()


def test_init_db_creates_tables_and_loads_csv_counts(
    tmp_path: Path,
    project_root: Path,
    table_names: tuple[str, ...],
    csv_row_counts: dict[str, int],
) -> None:
    db_path = tmp_path / "sample.db"

    db.init_db(
        db_path=db_path,
        schema_path=project_root / "schema.sql",
        csv_dir=project_root / "data",
    )

    with sqlite3.connect(db_path) as connection:
        assert _read_table_names(connection) == set(table_names)
        assert {
            table_name: _count_rows(connection, table_name)
            for table_name in table_names
        } == csv_row_counts


def test_get_readonly_connection_rejects_insert(
    tmp_db_path: Path,
    csv_row_counts: dict[str, int],
) -> None:
    with closing(db.get_readonly_connection(tmp_db_path)) as connection:
        with pytest.raises(
            sqlite3.OperationalError,
            match="readonly|read-only|attempt to write",
        ):
            _insert_customer(connection)

    with sqlite3.connect(tmp_db_path) as connection:
        assert _count_rows(connection, "customers") == csv_row_counts["customers"]
