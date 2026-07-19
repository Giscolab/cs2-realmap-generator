from __future__ import annotations

import json
import ssl
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import overpass_client  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict):
        self._content = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._content

    def getcode(self) -> int:
        return 200


def test_query_with_retry_uses_stdlib_http_and_decodes_json() -> None:
    original_endpoints = overpass_client.ENDPOINTS
    original_urlopen = overpass_client.urllib.request.urlopen
    captured = {}

    def fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["timeout"] = timeout
        captured["context"] = context
        return _FakeResponse({"elements": [{"id": 1}]})

    try:
        overpass_client.ENDPOINTS = ["https://example.invalid/api/interpreter"]
        overpass_client.urllib.request.urlopen = fake_urlopen
        result = overpass_client.query_with_retry("[out:json];node(0,0,1,1);out;", "test", 1)
    finally:
        overpass_client.ENDPOINTS = original_endpoints
        overpass_client.urllib.request.urlopen = original_urlopen

    assert result == {"elements": [{"id": 1}]}
    assert captured["url"] == "https://example.invalid/api/interpreter"
    assert b"data=%5Bout%3Ajson%5D" in captured["data"]
    assert captured["timeout"] == 200
    assert captured["context"] is overpass_client.SSL_CONTEXT
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["context"].check_hostname is True
