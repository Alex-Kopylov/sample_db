"""Shared fixtures for Postgres-backed security tests."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from sample_db.config import get_settings

EXPECTED_TABLES = ("customers", "products", "orders", "order_items")


@pytest.fixture(scope="session")
def table_names() -> tuple[str, ...]:
    """Return the expected public table names."""
    return EXPECTED_TABLES


@pytest.fixture(scope="session")
def require_postgres() -> None:
    """Skip tests when the local Postgres test database is unavailable."""
    try:
        settings = get_settings()
        for dsn in (settings.pg_app_dsn, settings.pg_auth_dsn):
            with psycopg.connect(dsn, connect_timeout=2) as connection:
                connection.execute("SELECT 1")
    except Exception as exc:
        pytest.skip(f"Postgres test database is unavailable: {exc}")


@pytest.fixture
def customer_config() -> dict[str, dict[str, dict[str, str]]]:
    """Return a LangGraph config carrying authenticated customer identity 7."""
    return {"configurable": {"langgraph_auth_user": {"identity": "7"}}}


@pytest.fixture
def app_connection(require_postgres: None) -> Iterator[psycopg.Connection]:
    """Open a sample_app connection for direct RLS assertions."""
    settings = get_settings()
    with psycopg.connect(settings.pg_app_dsn) as connection:
        yield connection
