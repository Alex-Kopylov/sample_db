"""Tests for LangGraph JWT authentication."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langgraph_sdk.auth.exceptions import HTTPException

import sample_db.auth as auth_module
from sample_db.auth import add_owner, authenticate
from sample_db.mint_token import mint_token


def _authenticate(authorization: str | None) -> dict[str, str]:
    headers = {"Authorization": authorization} if authorization is not None else {}
    return asyncio.run(authenticate(headers))


def _assert_unauthorized(exc_info: pytest.ExceptionInfo[HTTPException]) -> None:
    assert exc_info.value.status_code == 401


def test_authenticate_valid_token_returns_customer_identity(require_postgres: None) -> None:
    token = mint_token("user_007@example.test")

    user = _authenticate(f"Bearer {token}")

    assert user["identity"] == "7"
    assert user["email"] == "user_007@example.test"


def test_authenticate_garbage_token_raises_401(require_postgres: None) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _authenticate("Bearer not-a-jwt")

    _assert_unauthorized(exc_info)


def test_authenticate_expired_token_raises_401(require_postgres: None) -> None:
    token = mint_token("user_007@example.test", minutes=-1)

    with pytest.raises(HTTPException) as exc_info:
        _authenticate(f"Bearer {token}")

    _assert_unauthorized(exc_info)


def test_authenticate_unknown_email_raises_401(require_postgres: None) -> None:
    token = mint_token("unknown@example.test")

    with pytest.raises(HTTPException) as exc_info:
        _authenticate(f"Bearer {token}")

    _assert_unauthorized(exc_info)


def test_authenticate_accepts_case_insensitive_header_names(
    stub_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = mint_token("user_007@example.test")
    monkeypatch.setattr(auth_module.db, "resolve_customer_id_by_email", lambda _email: 7)

    user = asyncio.run(authenticate({"authorization": f"Bearer {token}"}))

    assert user == {"identity": "7", "email": "user_007@example.test"}


def test_authenticate_accepts_byte_headers(
    stub_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = mint_token("user_007@example.test")
    monkeypatch.setattr(auth_module.db, "resolve_customer_id_by_email", lambda _email: 7)

    user = asyncio.run(authenticate({b"Authorization": f"Bearer {token}".encode()}))

    assert user == {"identity": "7", "email": "user_007@example.test"}


def test_add_owner_replaces_null_metadata() -> None:
    ctx = SimpleNamespace(user=SimpleNamespace(identity="7"))
    value = {"metadata": None}

    filters = asyncio.run(add_owner(ctx, value))

    assert filters == {"owner": "7"}
    assert value["metadata"] == {"owner": "7"}
