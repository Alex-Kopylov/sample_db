"""Shared fixtures for sample database tests."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sample_db import db

EXPECTED_TABLES = ("customers", "products", "orders", "order_items")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


@pytest.fixture
def project_root() -> Path:
    """Return the repository root that holds schema.sql and CSV files."""
    return PROJECT_ROOT


@pytest.fixture
def table_names() -> tuple[str, ...]:
    """Return the expected sample database table names."""
    return EXPECTED_TABLES


@pytest.fixture
def csv_rows_by_table(
    project_root: Path,
    table_names: tuple[str, ...],
) -> dict[str, list[dict[str, str]]]:
    """Return parsed data rows from each root-level CSV file."""
    return {
        table_name: _read_csv_rows(project_root / f"{table_name}.csv")
        for table_name in table_names
    }


@pytest.fixture
def csv_row_counts(
    csv_rows_by_table: dict[str, list[dict[str, str]]],
) -> dict[str, int]:
    """Return the number of data rows in each root-level CSV file."""
    return {
        table_name: len(rows)
        for table_name, rows in csv_rows_by_table.items()
    }


@pytest.fixture
def tmp_db_path(tmp_path: Path, project_root: Path) -> Path:
    """Build a temporary SQLite database from the real schema and CSVs."""
    db_path = tmp_path / "app.db"
    db.init_db(
        db_path=db_path,
        schema_path=project_root / "schema.sql",
        csv_dir=project_root,
    )
    return db_path
