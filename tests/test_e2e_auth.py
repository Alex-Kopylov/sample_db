"""Unit coverage for the e2e HTTP transport."""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_E2E_AUTH_PATH = Path(__file__).resolve().parents[1] / "e2e_auth.py"
_E2E_AUTH_SPEC = importlib.util.spec_from_file_location("e2e_auth", _E2E_AUTH_PATH)
assert _E2E_AUTH_SPEC is not None
assert _E2E_AUTH_SPEC.loader is not None
e2e_auth = importlib.util.module_from_spec(_E2E_AUTH_SPEC)
_E2E_AUTH_SPEC.loader.exec_module(e2e_auth)


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def _request_json(req: urllib.request.Request) -> dict[str, Any]:
    data = req.data
    assert data is not None
    return json.loads(data.decode())


def test_post_run_uses_thread_based_runs_wait(monkeypatch) -> None:
    requests: list[urllib.request.Request] = []

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> _FakeResponse:
        requests.append(req)
        assert timeout == 150
        if req.full_url.endswith("/threads"):
            return _FakeResponse(200, {"thread_id": "thread-123"})
        if req.full_url.endswith("/threads/thread-123/runs/wait"):
            return _FakeResponse(200, {"messages": [{"content": "ok"}]})
        raise AssertionError(f"unexpected URL: {req.full_url}")

    monkeypatch.setattr(e2e_auth.urllib.request, "urlopen", fake_urlopen)

    status, state = e2e_auth.post_run("hello", "token-123")

    assert status == 200
    assert state == {"messages": [{"content": "ok"}]}
    assert [req.full_url for req in requests] == [
        f"{e2e_auth.SERVER}/threads",
        f"{e2e_auth.SERVER}/threads/thread-123/runs/wait",
    ]
    assert _request_json(requests[0]) == {}
    assert _request_json(requests[1]) == {
        "assistant_id": "sql_agent",
        "input": {"messages": [{"role": "user", "content": "hello"}]},
    }
    assert requests[0].headers["Authorization"] == "Bearer token-123"
    assert requests[1].headers["Authorization"] == "Bearer token-123"


def test_post_run_returns_first_non_2xx_from_thread_creation(monkeypatch) -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: int) -> _FakeResponse:
        assert req.full_url.endswith("/threads")
        raise urllib.error.HTTPError(
            req.full_url,
            401,
            "Unauthorized",
            hdrs={},
            fp=io.BytesIO(b"missing token"),
        )

    monkeypatch.setattr(e2e_auth.urllib.request, "urlopen", fake_urlopen)

    status, state = e2e_auth.post_run("hello", None)

    assert status == 401
    assert state == {"_error": "missing token"}
