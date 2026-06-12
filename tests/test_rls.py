"""Direct Postgres RLS assertions for the sample_app role."""

from __future__ import annotations

import psycopg


def _fetch_ids(
    connection: psycopg.Connection,
    customer_id: int,
    query: str = "SELECT id FROM customers ORDER BY id",
) -> list[int]:
    with connection.transaction():
        connection.execute(
            "SELECT set_config('app.customer_id', %s, true)",
            (str(customer_id),),
        )
        rows = connection.execute(query).fetchall()
    return [int(row[0]) for row in rows]


def _fetch_unscoped_ids(connection: psycopg.Connection) -> list[int]:
    with connection.transaction():
        rows = connection.execute("SELECT id FROM customers ORDER BY id").fetchall()
    return [int(row[0]) for row in rows]


def test_customer_7_sees_only_their_customer_row(app_connection: psycopg.Connection) -> None:
    assert _fetch_ids(app_connection, 7) == [7]


def test_customer_7_cannot_filter_to_customer_8(app_connection: psycopg.Connection) -> None:
    assert _fetch_ids(app_connection, 7, "SELECT id FROM customers WHERE id = 8") == []


def test_tautology_does_not_bypass_customer_7_policy(app_connection: psycopg.Connection) -> None:
    assert _fetch_ids(app_connection, 7, "SELECT id FROM customers WHERE id = 8 OR 1 = 1 ORDER BY id") == [7]


def test_unset_customer_guc_returns_no_customer_rows(app_connection: psycopg.Connection) -> None:
    assert _fetch_unscoped_ids(app_connection) == []


def test_switching_to_customer_8_is_disjoint(app_connection: psycopg.Connection) -> None:
    customer_7_ids = _fetch_ids(app_connection, 7)
    customer_8_ids = _fetch_ids(app_connection, 8)

    assert customer_8_ids == [8]
    assert set(customer_7_ids).isdisjoint(customer_8_ids)
