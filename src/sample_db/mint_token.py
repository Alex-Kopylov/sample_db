"""Mint JWTs for authenticated LangGraph SQL agent requests."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt

from sample_db.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence


def mint_token(email: str, minutes: int = 60) -> str:
    """Return a signed JWT for a customer email."""
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=minutes)
    payload = {
        "sub": email,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the token minting command-line interface."""
    parser = argparse.ArgumentParser(description="Mint a sample-db JWT")
    parser.add_argument("email")
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args(argv)

    print(mint_token(args.email, minutes=args.minutes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
