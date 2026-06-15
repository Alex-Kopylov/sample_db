"""Postgres connection helpers for tenant-scoped agent queries."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import psycopg

from sample_db.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

FORBIDDEN_TENANT_SQL_PATTERNS = (
    re.compile(r"\bset_config\s*\(", flags=re.IGNORECASE),
    re.compile(r"\bapp\s*\.\s*customer_id\b", flags=re.IGNORECASE),
)


def app_connection() -> psycopg.Connection:
    """Open a connection as the RLS-enforced sample_app role."""
    return psycopg.connect(get_settings().pg_app_dsn)


def auth_connection() -> psycopg.Connection:
    """Open a connection as the sample_auth lookup role."""
    return psycopg.connect(get_settings().pg_auth_dsn)


def run_tenant_query(
    customer_id: int,
    sql: str,
    params: Sequence[Any] = (),
) -> list[tuple[Any, ...]]:
    """Run a query inside a transaction scoped to one customer id."""
    _ensure_query_cannot_change_tenant(sql)
    with app_connection() as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute(
            "SELECT set_config('app.customer_id', %s, true)",
            (str(customer_id),),
        )
        cursor = connection.execute(sql, params)
        return cursor.fetchmany(50)


def resolve_customer_id_by_email(email: str) -> int | None:
    """Return a customer id for an email using the auth-only database role."""
    with auth_connection() as connection:
        row = connection.execute(
            "SELECT id FROM customers WHERE email = %s",
            (email,),
        ).fetchone()

    if row is None:
        return None
    return int(row[0])


def _ensure_query_cannot_change_tenant(sql: str) -> None:
    if any(pattern.search(sql) for pattern in FORBIDDEN_TENANT_SQL_PATTERNS):
        msg = "Query cannot reference or modify tenant scope"
        raise PermissionError(msg)
