"""Tests for tenant-scoped database execution helpers."""

from __future__ import annotations

from typing import Any

from sample_db import db


class _FakeCursor:
    def fetchmany(self, _size: int) -> list[tuple[str]]:
        return [("ok",)]


class _FakeTransaction:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _FakeCursor:
        self.executed.append((sql, params))
        return _FakeCursor()


def test_run_tenant_query_marks_transaction_read_only(monkeypatch) -> None:
    connection = _FakeConnection()
    monkeypatch.setattr(db, "app_connection", lambda: connection)

    result = db.run_tenant_query(7, "SELECT id FROM customers")

    assert result == [("ok",)]
    assert connection.executed == [
        ("SET TRANSACTION READ ONLY", ()),
        ("SELECT set_config('app.customer_id', %s, true)", ("7",)),
        ("SELECT id FROM customers", ()),
    ]
