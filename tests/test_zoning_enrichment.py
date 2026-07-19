from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from classifiers import classify_commercial  # noqa: E402
from cs2_zones import build_queries  # noqa: E402


def test_commercial_query_includes_dense_buildings_and_malls() -> None:
    query = build_queries("0,0,1,1")["commercial"]

    assert 'building"~"^(commercial|retail|mall)$"' in query
    assert 'shop"~"^(mall|department_store)$"' in query


def test_commercial_density_uses_levels_and_large_retail_types() -> None:
    assert classify_commercial({"building": "commercial", "building:levels": "5"}) == "high"
    assert classify_commercial({"shop": "mall"}) == "high"
    assert classify_commercial({"landuse": "commercial"}) == "low"


def test_mixed_query_covers_explicit_and_multi_use_buildings() -> None:
    query = build_queries("0,0,1,1")["mixed"]

    assert 'building"~"^(mixed|mixed-use|mixed_use)$"' in query
    assert 'mixed_use"="yes"' in query
    assert 'building:use"~"(apartments|residential)"' in query
    assert 'building:use"~"(commercial|office|retail|shop)"' in query
