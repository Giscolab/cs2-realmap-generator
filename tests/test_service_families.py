from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from service_families import (  # noqa: E402
    SERVICE_FAMILIES,
    build_service_query,
    classify_service_element,
    implemented_families,
    service_point,
    source_tag,
)


def family(key: str) -> dict:
    return next(f for f in SERVICE_FAMILIES if f["key"] == key)


def test_nine_families_declared() -> None:
    assert len(SERVICE_FAMILIES) == 9


def test_four_families_implemented() -> None:
    keys = {f["key"] for f in implemented_families()}
    assert keys == {"education", "fire", "medical", "parks"}


def test_query_builder_emits_node_way_relation_and_center() -> None:
    q = build_service_query(family("fire"), "48.8,2.3,48.9,2.4")
    assert q is not None
    assert 'node["amenity"~"^(fire_station)$"](48.8,2.3,48.9,2.4);' in q
    assert 'way["amenity"~"^(fire_station)$"](48.8,2.3,48.9,2.4);' in q
    assert 'relation["amenity"~"^(fire_station)$"](48.8,2.3,48.9,2.4);' in q
    assert "out center tags;" in q


def test_query_builder_merges_subcategory_selectors() -> None:
    q = build_service_query(family("medical"), "0,0,1,1")
    # hôpital + clinique + crématorium regroupés sous la clé amenity
    assert "hospital" in q and "clinic" in q and "crematorium" in q and "grave_yard" in q
    # cimetière via landuse aussi présent
    assert 'landuse"~"^(cemetery)$"' in q


def test_unimplemented_family_has_no_query() -> None:
    assert build_service_query(family("electricity"), "0,0,1,1") is None


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "hospital"}, "hospital"),
    ({"amenity": "clinic"}, "clinic"),
    ({"amenity": "doctors"}, "clinic"),
    ({"amenity": "crematorium"}, "crematorium"),
    ({"landuse": "cemetery"}, "cemetery"),
    ({"amenity": "grave_yard"}, "cemetery"),
    ({"shop": "bakery"}, None),
])
def test_classify_medical(tags, expected) -> None:
    assert classify_service_element(family("medical"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "school"}, "primary"),
    ({"amenity": "kindergarten"}, "primary"),
    ({"amenity": "university"}, "university"),
    ({"office": "research"}, "research"),
])
def test_classify_education(tags, expected) -> None:
    assert classify_service_element(family("education"), tags) == expected


def test_classify_parks_order_is_deterministic() -> None:
    assert classify_service_element(family("parks"), {"leisure": "park"}) == "local_park"
    assert classify_service_element(family("parks"), {"leisure": "stadium"}) == "sport"
    assert classify_service_element(family("parks"), {"tourism": "museum"}) == "tourism"


def test_service_point_from_node() -> None:
    el = {"type": "node", "lat": 48.85, "lon": 2.35, "tags": {"amenity": "hospital"}}
    assert service_point(el) == [48.85, 2.35]


def test_service_point_from_way_center() -> None:
    el = {"type": "way", "center": {"lat": 48.86, "lon": 2.36}, "tags": {"amenity": "school"}}
    assert service_point(el) == [48.86, 2.36]


def test_service_point_none_when_missing() -> None:
    assert service_point({"type": "way", "tags": {"amenity": "school"}}) is None


def test_source_tag() -> None:
    assert source_tag(family("medical"), {"amenity": "hospital"}) == "amenity=hospital"
    assert source_tag(family("medical"), {"landuse": "cemetery"}) == "landuse=cemetery"
