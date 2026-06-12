"""Tests for LangGraph JWT authentication."""

from __future__ import annotations

import asyncio

import pytest
from langgraph_sdk.auth.exceptions import HTTPException

from sample_db.auth import authenticate
from sample_db.mint_token import mint_token


def _authenticate(authorization: str | None) -> dict[str, str]:
    return asyncio.run(authenticate(authorization))


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
