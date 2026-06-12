"""LangChain tools for inspecting and querying the SQLite database."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from langchain.tools import tool

if TYPE_CHECKING:
    from collections.abc import Iterable

from sample_db import db
from sample_db.config import get_settings


@tool
def sql_db_list_tables() -> str:
    """Input is an empty string, output is a comma-separated list of tables."""
    connection = db.get_readonly_connection(get_settings().db_path)
    try:
        cursor = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
        )
        return ", ".join(row[0] for row in cursor.fetchall())
    finally:
        connection.close()


@tool
def sql_db_schema(table_names: str) -> str:
    """Input is a comma-separated list of tables; output is schema and sample rows."""
    connection = db.get_readonly_connection(get_settings().db_path)
    try:
        valid_tables = _list_table_names(connection)
        results: list[str] = []

        for table_name in _parse_table_names(table_names):
            if table_name not in valid_tables:
                results.append(
                    f"Error: table_names {{{table_name!r}}} not found in database"
                )
                continue

            schema_row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?;",
                (table_name,),
            ).fetchone()
            if schema_row is None:
                results.append(
                    f"Error: table_names {{{table_name!r}}} not found in database"
                )
                continue

            results.extend((schema_row[0], _format_sample_rows(connection, table_name)))

        return "\n\n".join(results)
    finally:
        connection.close()


@tool
def sql_db_query(query: str) -> str:
    """Input is a SQL query; output is the database result or an error message."""
    connection = db.get_readonly_connection(get_settings().db_path)
    try:
        cursor = connection.execute(query)
        return str(cursor.fetchmany(50))
    except sqlite3.Error as error:
        return f"Error: {error}"
    finally:
        connection.close()


def _list_table_names(connection: sqlite3.Connection) -> set[str]:
    cursor = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
    )
    return {row[0] for row in cursor.fetchall()}


def _parse_table_names(table_names: str) -> Iterable[str]:
    return (
        table_name.strip()
        for table_name in table_names.split(",")
        if table_name.strip()
    )


def _format_sample_rows(connection: sqlite3.Connection, table_name: str) -> str:
    quoted_table_name = _quote_identifier(table_name)
    cursor = connection.execute(
        f"SELECT * FROM {quoted_table_name} LIMIT 3;"  # noqa: S608 - identifier quoted via _quote_identifier
    )
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]

    return (
        f"/*\n3 sample rows from {table_name} table:\n"
        + "\t".join(column_names)
        + "\n"
        + "\n".join("\t".join(str(value) for value in row) for row in rows)
        + "\n*/"
    )


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
