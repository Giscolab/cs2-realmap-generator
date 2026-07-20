from __future__ import annotations

import json
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
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


def test_query_cache_resumes_without_a_second_http_request() -> None:
    original_endpoints = overpass_client.ENDPOINTS
    original_urlopen = overpass_client.urllib.request.urlopen
    calls = []
    query = "[out:json];node(0,0,1,1);out;"

    def fake_urlopen(request, timeout, context):
        calls.append(request.full_url)
        return _FakeResponse({"elements": [{"type": "node", "id": 7}]})

    try:
        overpass_client.ENDPOINTS = ["https://example.invalid/api/interpreter"]
        overpass_client.urllib.request.urlopen = fake_urlopen
        with tempfile.TemporaryDirectory() as temporary:
            first = overpass_client.query_with_retry(
                query, "resume-test", 1, cache_dir=temporary
            )
            second = overpass_client.query_with_retry(
                query, "resume-test", 1, cache_dir=temporary
            )
            cache_files = list(Path(temporary).glob("resume-test-*.json"))
    finally:
        overpass_client.ENDPOINTS = original_endpoints
        overpass_client.urllib.request.urlopen = original_urlopen

    assert first == second == {"elements": [{"type": "node", "id": 7}]}
    assert calls == ["https://example.invalid/api/interpreter"]
    assert len(cache_files) == 1


def test_failed_large_bbox_is_split_and_merged_without_duplicates() -> None:
    original_endpoints = overpass_client.ENDPOINTS
    original_urlopen = overpass_client.urllib.request.urlopen
    original_sleep = overpass_client.time.sleep
    calls = []

    def fake_urlopen(request, timeout, context):
        overpass_query = urllib.parse.parse_qs(request.data.decode("utf-8"))["data"][0]
        calls.append(overpass_query)
        if "(0,0,2,2)" in overpass_query:
            raise urllib.error.URLError("requête trop grande")
        tile_id = len(calls)
        return _FakeResponse({
            "elements": [
                {"type": "way", "id": 1},
                {"type": "way", "id": tile_id},
            ]
        })

    try:
        overpass_client.ENDPOINTS = ["https://example.invalid/api/interpreter"]
        overpass_client.urllib.request.urlopen = fake_urlopen
        overpass_client.time.sleep = lambda _seconds: None
        result = overpass_client.query_with_retry(
            '[out:json];way["highway"](0,0,2,2);out geom;',
            "adaptive-test",
            1,
            split_bbox_on_failure=True,
            max_split_depth=1,
        )
    finally:
        overpass_client.ENDPOINTS = original_endpoints
        overpass_client.urllib.request.urlopen = original_urlopen
        overpass_client.time.sleep = original_sleep

    assert len(calls) == 5
    assert [element["id"] for element in result["elements"]] == [1, 2, 3, 4, 5]
