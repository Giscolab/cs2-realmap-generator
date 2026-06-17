from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Le module importe numpy / PIL : on saute proprement si absents.
pytest.importorskip("numpy")
pytest.importorskip("PIL")

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from export_terrain_rgb_png import _redact_secrets  # noqa: E402


def test_redacts_maptiler_key() -> None:
    url = "https://api.maptiler.com/tiles/terrain-rgb-v2/14/8/5.webp?key=SECRET123"
    out = _redact_secrets(url)
    assert "SECRET123" not in out
    assert "key=***" in out


def test_redacts_mapbox_token_and_keeps_other_params() -> None:
    msg = "HTTP 401 sur .../tile.pngraw?access_token=pk.SECRET&foo=bar"
    out = _redact_secrets(msg)
    assert "pk.SECRET" not in out
    assert "access_token=***" in out
    assert "foo=bar" in out


def test_non_secret_text_unchanged() -> None:
    assert _redact_secrets("erreur réseau timeout") == "erreur réseau timeout"
