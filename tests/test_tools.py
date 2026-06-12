"""Tests for sample_db.tools."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from sample_db import tools


@pytest.fixture
def configured_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_db_path: Path,
) -> Path:
    monkeypatch.setattr(
        tools,
        "get_settings",
        lambda: SimpleNamespace(db_path=tmp_db_path),
    )
    return tmp_db_path


def _parse_table_list(result: str) -> set[str]:
    return {
        table_name.strip()
        for table_name in result.split(",")
        if table_name.strip()
    }


def _count_customers(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM customers;").fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.usefixtures("configured_tools")
def test_sql_db_list_tables_returns_all_tables(table_names: tuple[str, ...]) -> None:
    result = tools.sql_db_list_tables.invoke({})

    assert _parse_table_list(result) == set(table_names)


@pytest.mark.usefixtures("configured_tools")
def test_sql_db_schema_includes_create_statement_and_sample_rows(
    csv_rows_by_table: dict[str, list[dict[str, str]]],
) -> None:
    result = tools.sql_db_schema.invoke({"table_names": "customers"})
    first_customer = csv_rows_by_table["customers"][0]
    customer_columns = tuple(first_customer)

    assert "CREATE TABLE customers" in result
    assert "3 sample rows from customers table:" in result
    assert "\t".join(customer_columns) in result
    assert "\t".join(first_customer[column] for column in customer_columns) in result


@pytest.mark.usefixtures("configured_tools")
def test_sql_db_query_returns_customer_count(
    csv_row_counts: dict[str, int],
) -> None:
    result = tools.sql_db_query.invoke({"query": "SELECT COUNT(*) FROM customers"})

    assert result == f"[({csv_row_counts['customers']},)]"


def test_sql_db_query_insert_returns_error_and_does_not_mutate(
    configured_tools: Path,
    csv_row_counts: dict[str, int],
) -> None:
    insert_result = tools.sql_db_query.invoke(
        {
            "query": (
                "INSERT INTO customers (id, name, email, country, created_at) "
                "VALUES (999999, 'Readonly User', 'readonly@example.com', 'US', '2026-01-01');"
            ),
        }
    )

    assert insert_result.startswith("Error:")
    assert _count_customers(configured_tools) == csv_row_counts["customers"]
