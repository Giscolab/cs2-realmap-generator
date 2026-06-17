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


def test_all_families_implemented() -> None:
    keys = {f["key"] for f in implemented_families()}
    assert keys == {
        "communications",
        "education",
        "electricity",
        "fire",
        "medical",
        "parks",
        "transport",
        "waste",
        "water",
    }


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


@pytest.mark.parametrize("family_key", [
    "communications",
    "education",
    "electricity",
    "fire",
    "medical",
    "parks",
    "transport",
    "waste",
    "water",
])
def test_all_families_have_query(family_key) -> None:
    assert build_service_query(family(family_key), "0,0,1,1") is not None


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


@pytest.mark.parametrize("tags,expected", [
    ({"power": "plant"}, "generation"),
    ({"power": "substation"}, "transformation"),
    ({"power": "storage"}, "storage"),
    ({"power": "tower"}, "grid"),
])
def test_classify_electricity(tags, expected) -> None:
    assert classify_service_element(family("electricity"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "waste_disposal"}, "collection"),
    ({"amenity": "recycling"}, "recycling"),
    ({"man_made": "incinerator"}, "treatment"),
    ({"landuse": "landfill"}, "landfill"),
])
def test_classify_waste(tags, expected) -> None:
    assert classify_service_element(family("waste"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"highway": "bus_stop"}, "bus"),
    ({"railway": "tram_stop"}, "tram"),
    ({"railway": "station"}, "train"),
    ({"railway": "subway_entrance"}, "metro"),
    ({"amenity": "taxi"}, "taxi"),
    ({"aeroway": "aerodrome"}, "air"),
    ({"amenity": "ferry_terminal"}, "maritime"),
])
def test_classify_transport(tags, expected) -> None:
    assert classify_service_element(family("transport"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"man_made": "pumping_station"}, "pumping"),
    ({"man_made": "water_works"}, "water_treatment"),
    ({"waterway": "drain"}, "sewage"),
    ({"man_made": "wastewater_plant"}, "wastewater"),
])
def test_classify_water(tags, expected) -> None:
    assert classify_service_element(family("water"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "post_office"}, "post"),
    ({"telecom": "exchange"}, "telecom"),
    ({"building": "data_center"}, "datacenter"),
    ({"tower:type": "communication"}, "radio"),
])
def test_classify_communications(tags, expected) -> None:
    assert classify_service_element(family("communications"), tags) == expected


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
