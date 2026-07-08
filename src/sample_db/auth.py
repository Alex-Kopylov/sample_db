"""LangGraph authentication hooks for JWT-backed customer identity."""

from __future__ import annotations

from typing import TYPE_CHECKING

import jwt
from langgraph_sdk import Auth

from sample_db import db
from sample_db.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping

auth = Auth()


class AuthenticatedUserDict(Auth.types.MinimalUserDict):
    """Resolved customer identity returned by the authenticate hook.

    Extends the SDK's ``MinimalUserDict`` with the customer's email claim;
    the ``Authenticator`` contract allows extra mapping keys at runtime.
    """

    email: str


INVALID_SUBJECT_DETAIL = "Invalid token subject"
INVALID_JWT_DETAIL = "Invalid token"
MISSING_AUTHORIZATION_DETAIL = "Missing authorization header"
MISSING_BEARER_DETAIL = "Missing bearer token"
UNKNOWN_CUSTOMER_DETAIL = "Unknown authenticated customer"
UNRESOLVED_CUSTOMER_DETAIL = "Unable to resolve authenticated customer"


@auth.authenticate
async def authenticate(  # noqa: RUF029
    headers: Mapping[str | bytes, str | bytes] | str | bytes | None,
) -> AuthenticatedUserDict:
    """Authenticate a bearer token and return the resolved customer identity."""
    authorization = _authorization_from_headers(headers)
    token = _extract_bearer_token(authorization)
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized(INVALID_JWT_DETAIL) from exc

    email = payload.get("sub")
    if not isinstance(email, str) or not email:
        raise _unauthorized(INVALID_SUBJECT_DETAIL)

    try:
        customer_id = db.resolve_customer_id_by_email(email)
    except Exception as exc:
        raise _unauthorized(UNRESOLVED_CUSTOMER_DETAIL) from exc

    if customer_id is None:
        raise _unauthorized(UNKNOWN_CUSTOMER_DETAIL)

    return {"identity": str(customer_id), "email": email}


@auth.on
async def add_owner(ctx, value):  # noqa: RUF029
    """Stamp created resources with the authenticated owner identity."""
    metadata = value.get("metadata") if isinstance(value, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
        if isinstance(value, dict):
            value["metadata"] = metadata
    metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}


def _authorization_from_headers(
    headers: Mapping[str | bytes, str | bytes] | str | bytes | None,
) -> str | None:
    if isinstance(headers, str):
        return headers
    if isinstance(headers, bytes):
        return _decode_header(headers)
    if headers is None:
        return None

    for key, value in headers.items():
        normalized_key = _decode_header(key).lower()
        if normalized_key == "authorization":
            return _decode_header(value)
    return None


def _decode_header(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("latin-1")
    return value


def _extract_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise _unauthorized(MISSING_AUTHORIZATION_DETAIL)

    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized(MISSING_BEARER_DETAIL)

    return token


def _unauthorized(detail: str) -> Auth.exceptions.HTTPException:
    return Auth.exceptions.HTTPException(status_code=401, detail=detail)
