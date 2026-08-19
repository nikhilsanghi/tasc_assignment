"""Shared API plumbing: access control, response envelope, dispatch, handler factory."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import hmac
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler


def check_access(headers: dict) -> bool:
    code = os.environ.get("ACCESS_CODE", "")
    if not code:
        return False
    provided = ""
    for key, value in headers.items():
        if key.lower() == "x-access-code":
            provided = value
            break
    return hmac.compare_digest(code, provided)


def meta(usage: dict | None = None, prompt_hash: str | None = None) -> dict:
    return {
        "model": os.environ.get("MODEL_REASONING", "claude-sonnet-5"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usage": usage,
        "prompt_hash": prompt_hash,
    }


def dispatch(handle, headers: dict, body: dict) -> tuple[int, dict]:
    """D-50: LLMRateLimited->429 / LLMOutputError->502 map in once core/llm.py exists (Phase 2)."""
    if not check_access(headers):
        return 401, {"error": "unauthorized"}
    try:
        return handle(body, headers)
    except Exception as e:
        return 500, {"error": "internal", "detail": str(e)}


class APIHandler(BaseHTTPRequestHandler):
    """D-51: each api/<name>.py subclasses this with a literal `class handler(...)`
    statement (never `handler = <expr>`) - Vercel's build-time function detector only
    recognizes a literal class statement, not a factory-produced/assigned class."""

    handle_fn = staticmethod(lambda body, headers: (501, {"error": "not_implemented"}))
    methods: tuple = ("POST",)

    def _respond(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else {}
        headers = dict(self.headers.items())
        status, payload = dispatch(self.handle_fn, headers, body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_POST(self) -> None:
        if "POST" in self.methods:
            self._respond()

    def do_GET(self) -> None:
        if "GET" in self.methods:
            self._respond()
