"""Tests for tenant-scoped LangChain SQL tools."""

from __future__ import annotations

import pytest

from sample_db import tools


def _parse_table_list(result: str) -> set[str]:
    return {table_name.strip() for table_name in result.split(",") if table_name.strip()}


def test_sql_db_list_tables_returns_public_tables(
    require_postgres: None,
    customer_config: dict[str, dict[str, dict[str, str]]],
    table_names: tuple[str, ...],
) -> None:
    result = tools.sql_db_list_tables.invoke({}, config=customer_config)

    assert _parse_table_list(result) == set(table_names)


def test_sql_db_query_uses_authenticated_customer_config(
    require_postgres: None,
    customer_config: dict[str, dict[str, dict[str, str]]],
) -> None:
    result = tools.sql_db_query.invoke(
        {"query": "SELECT id, email FROM customers ORDER BY id"},
        config=customer_config,
    )

    assert "user_007@example.test" in result
    assert "user_008@example.test" not in result
    assert "(7," in result
    assert "(8," not in result


def test_sql_db_query_runs_inside_read_only_transaction(
    require_postgres: None,
    customer_config: dict[str, dict[str, dict[str, str]]],
) -> None:
    result = tools.sql_db_query.invoke(
        {"query": "SHOW transaction_read_only"},
        config=customer_config,
    )

    assert result == "[('on',)]"


def test_sql_db_schema_returns_columns_without_sample_rows(
    require_postgres: None,
    customer_config: dict[str, dict[str, dict[str, str]]],
) -> None:
    result = tools.sql_db_schema.invoke(
        {"table_names": "customers"},
        config=customer_config,
    )

    assert "customers" in result
    assert "email" in result
    assert "3 sample rows" not in result
    assert "user_007@example.test" not in result
    assert "user_008@example.test" not in result


def test_sql_db_query_without_auth_user_raises() -> None:
    with pytest.raises(PermissionError):
        tools.sql_db_query.invoke({"query": "SELECT id FROM customers"})


def test_sql_db_query_rejects_tenant_scope_mutation(
    customer_config: dict[str, dict[str, dict[str, str]]],
) -> None:
    with pytest.raises(PermissionError):
        tools.sql_db_query.invoke(
            {"query": "SELECT set_config('app.customer_id', '8', true)"},
            config=customer_config,
        )


def test_sql_db_query_rejects_write_attempts(
    require_postgres: None,
    customer_config: dict[str, dict[str, dict[str, str]]],
) -> None:
    result = tools.sql_db_query.invoke(
        {"query": "DELETE FROM customers WHERE id = 7"},
        config=customer_config,
    )

    assert result.startswith("Error:")
