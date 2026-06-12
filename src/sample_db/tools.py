"""LangChain tools for tenant-scoped Postgres inspection and querying."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import psycopg
from langchain_core.runnables import (
    RunnableConfig,  # noqa: TC002 - LangChain excludes config from tool schemas by type.
)
from langchain_core.tools import tool

from sample_db import db

VALID_TABLES = ("customers", "products", "orders", "order_items")


def _current_customer_id(config: RunnableConfig) -> int:
    try:
        user = config["configurable"]["langgraph_auth_user"]
    except (KeyError, TypeError) as exc:
        msg = "Missing langgraph_auth_user"
        raise PermissionError(msg) from exc

    identity = user.get("identity") if isinstance(user, Mapping) else getattr(user, "identity", None)
    if identity is None:
        msg = "Missing authenticated user identity"
        raise PermissionError(msg)

    try:
        return int(identity)
    except (TypeError, ValueError) as exc:
        msg = "Invalid authenticated user identity"
        raise PermissionError(msg) from exc


@tool
def sql_db_list_tables(*, config: RunnableConfig) -> str:
    """Input is an empty object, output is a comma-separated list of tables."""
    _current_customer_id(config)
    return ", ".join(VALID_TABLES)


@tool
def sql_db_schema(table_names: str, *, config: RunnableConfig) -> str:
    """Input is a comma-separated list of tables; output is column names and types."""
    customer_id = _current_customer_id(config)
    requested_tables = tuple(_parse_table_names(table_names))
    requested_valid_tables = tuple(table_name for table_name in requested_tables if table_name in VALID_TABLES)
    results = [
        f"Error: table_names {{{table_name!r}}} not found in database"
        for table_name in requested_tables
        if table_name not in VALID_TABLES
    ]

    if requested_valid_tables:
        rows = db.run_tenant_query(
            customer_id,
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            ORDER BY table_name, ordinal_position
            """,
            (list(requested_valid_tables),),
        )
        results.extend(_format_schema_rows(rows, requested_valid_tables))

    return "\n\n".join(results)


@tool
def sql_db_query(query: str, *, config: RunnableConfig) -> str:
    """Input is a SQL query; output is the tenant-scoped database result or an error."""
    customer_id = _current_customer_id(config)
    try:
        return str(db.run_tenant_query(customer_id, query))
    except psycopg.Error as error:
        return f"Error: {error}"


def _parse_table_names(table_names: str) -> Iterable[str]:
    return (table_name.strip() for table_name in table_names.split(",") if table_name.strip())


def _format_schema_rows(
    rows: list[tuple[Any, ...]],
    requested_tables: tuple[str, ...],
) -> list[str]:
    rows_by_table: dict[str, list[tuple[str, str]]] = {table_name: [] for table_name in requested_tables}
    for table_name, column_name, data_type in rows:
        rows_by_table[str(table_name)].append((str(column_name), str(data_type)))

    results = []
    for table_name in requested_tables:
        columns = rows_by_table[table_name]
        if not columns:
            results.append(f"Error: table_names {{{table_name!r}}} not found in database")
            continue
        formatted_columns = "\n".join(f"- {column_name}: {data_type}" for column_name, data_type in columns)
        results.append(f"{table_name}\n{formatted_columns}")
    return results
