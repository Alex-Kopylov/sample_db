"""SQLite database initialization and connection helpers."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

TABLE_LOAD_ORDER = ("customers", "products", "orders", "order_items")

INTEGER_COLUMNS = {
    "customers": {"id"},
    "products": {"id", "price_cents"},
    "orders": {"id", "customer_id"},
    "order_items": {"id", "order_id", "product_id", "quantity", "unit_price_cents"},
}


def init_db(
    db_path: str | Path,
    schema_path: str | Path = "schema.sql",
    csv_dir: str | Path = "data",
) -> None:
    """Create the SQLite database from the schema and load CSV fixtures."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    schema = Path(schema_path).read_text(encoding="utf-8")
    csv_root = Path(csv_dir)

    with sqlite3.connect(db_file) as connection:
        connection.executescript(schema)
        connection.execute("PRAGMA foreign_keys = ON")

        for table_name in TABLE_LOAD_ORDER:
            _load_csv(
                connection=connection,
                table_name=table_name,
                csv_path=csv_root / f"{table_name}.csv",
            )


def get_readonly_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a read-only connection to the SQLite database."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _load_csv(
    connection: sqlite3.Connection,
    table_name: str,
    csv_path: Path,
) -> None:
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            msg = f"{csv_path} has no header row"
            raise ValueError(msg)

        columns = tuple(reader.fieldnames)
        placeholders = ", ".join("?" for _ in columns)
        column_names = ", ".join(_quote_identifier(column) for column in columns)
        statement = (
            f"INSERT INTO {_quote_identifier(table_name)} "  # noqa: S608 - identifiers quoted via _quote_identifier
            f"({column_names}) VALUES ({placeholders})"
        )
        rows = [
            tuple(
                _cast_csv_value(
                    table_name=table_name,
                    column=column,
                    value=row[column],
                )
                for column in columns
            )
            for row in reader
        ]

    connection.executemany(statement, rows)


def _cast_csv_value(table_name: str, column: str, value: str) -> int | str:
    if column in INTEGER_COLUMNS[table_name]:
        return int(value)
    return value


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
