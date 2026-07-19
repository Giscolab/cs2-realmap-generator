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
    service_tags,
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
    amenity_selector = '["amenity"~"^(coast_guard|fire_station|rescue_station)$"]'
    assert f"node{amenity_selector}(48.8,2.3,48.9,2.4);" in q
    assert f"way{amenity_selector}(48.8,2.3,48.9,2.4);" in q
    assert f"relation{amenity_selector}(48.8,2.3,48.9,2.4);" in q
    assert "out center tags;" in q


def test_query_builder_merges_subcategory_selectors() -> None:
    q = build_service_query(family("medical"), "0,0,1,1")
    # hôpital + clinique + crématorium regroupés sous la clé amenity
    assert "hospital" in q and "clinic" in q and "crematorium" in q and "grave_yard" in q
    # cimetière via landuse aussi présent
    assert 'landuse"~"^(cemetery)$"' in q


def test_query_builder_extracts_conditions_without_operator_pseudo_tags() -> None:
    q = build_service_query(family("education"), "0,0,1,1")
    assert q is not None
    assert '["school"~"^(elementary|high_school|junior|junior_high|middle|primary|secondary|senior_high)$"]' in q
    assert '["isced:level"~"^(0|1|2|3|4|5|6|7|8)$"]' in q
    assert '["all"' not in q
    assert '["any"' not in q
    assert '["name_contains"' not in q


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
    ({"amenity": "childcare"}, "primary"),
    ({"amenity": "school", "school": "secondary"}, "secondary"),
    ({"amenity": "school", "isced:level": "1;2;3"}, "secondary"),
    ({"amenity": "school", "min_age": "12"}, "secondary"),
    ({"amenity": "school", "grades": "7-12"}, "secondary"),
    ({"amenity": "school", "grades": "1-12"}, "secondary"),
    ({"amenity": "school", "isced:level": "6"}, "university"),
    ({"amenity": "school", "name": "Queanbeyan High School"}, "secondary"),
    ({"amenity": "school", "name": "Pretoria Hoërskool"}, "secondary"),
    ({"amenity": "school", "name": "Laerskool Pretoria"}, "primary"),
    # College/academy seuls sont trop ambigus pour forcer le secondaire.
    ({"amenity": "school", "name": "Canberra Grammar College"}, "primary"),
    ({"amenity": "university"}, "university"),
    ({"office": "research"}, "research"),
])
def test_classify_education(tags, expected) -> None:
    assert classify_service_element(family("education"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "fire_station"}, "local_station"),
    ({"emergency": "fire_station"}, "local_station"),
    ({"amenity": "fire_station", "fire_station:type": "headquarters"}, "large_station"),
    ({"amenity": "fire_station", "capacity:fire_engines": "6"}, "large_station"),
    ({"amenity": "fire_station", "name": "Central Fire Station"}, "large_station"),
    ({"emergency": "water_rescue"}, "special_rescue"),
    ({"emergency": "lifeguard", "lifeguard": "tower"}, "special_rescue"),
])
def test_classify_fire(tags, expected) -> None:
    assert classify_service_element(family("fire"), tags) == expected


def test_classify_parks_order_is_deterministic() -> None:
    assert classify_service_element(family("parks"), {"leisure": "park"}) == "local_park"
    assert classify_service_element(family("parks"), {"leisure": "stadium"}) == "sport"
    assert classify_service_element(family("parks"), {"tourism": "museum"}) == "tourism"


@pytest.mark.parametrize("tags,expected", [
    ({"power": "plant"}, "generation"),
    ({"power": "substation"}, "transformation"),
    ({"power": "storage"}, "storage"),
    ({"power": "generator", "generator:source": "solar;battery"}, "storage"),
    ({"power": "plant", "plant:method": "water-pumped-storage"}, "storage"),
    ({"man_made": "battery_storage"}, "storage"),
    ({"power": "tower"}, "grid"),
    ({"power": "switch"}, "grid"),
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
    ({"public_transport": "platform", "bus": "yes"}, "bus"),
    ({"railway": "tram_stop"}, "tram"),
    ({"railway": "station", "station": "light_rail"}, "tram"),
    ({"railway": "station"}, "train"),
    ({"railway": "subway_entrance"}, "metro"),
    ({"railway": "station", "station": "subway"}, "metro"),
    ({"public_transport": "platform", "subway": "yes", "train": "yes"}, "metro"),
    ({"amenity": "taxi"}, "taxi"),
    ({"aeroway": "aerodrome"}, "air"),
    ({"amenity": "ferry_terminal"}, "maritime"),
    ({"public_transport": "station", "ferry": "yes"}, "maritime"),
])
def test_classify_transport(tags, expected) -> None:
    assert classify_service_element(family("transport"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"man_made": "pumping_station"}, "pumping"),
    ({"man_made": "pumping_station", "pumping_station": "sewage"}, "sewage"),
    ({"man_made": "water_works"}, "water_treatment"),
    ({"industrial": "water_treatment"}, "water_treatment"),
    ({"waterway": "drain"}, "sewage"),
    ({"man_made": "wastewater_plant"}, "wastewater"),
    ({"man_made": "water_works", "water_works": "wastewater"}, "wastewater"),
])
def test_classify_water(tags, expected) -> None:
    assert classify_service_element(family("water"), tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "post_office"}, "post"),
    ({"amenity": "parcel_locker"}, "post"),
    ({"telecom": "exchange"}, "telecom"),
    ({"man_made": "street_cabinet", "street_cabinet": "telecom"}, "telecom"),
    ({"building": "data_center"}, "datacenter"),
    ({"building": "data_centre"}, "datacenter"),
    ({"tower:type": "communication"}, "radio"),
    ({"communication:mobile_phone": "yes"}, "radio"),
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
    assert source_tag(
        family("education"),
        {"amenity": "school", "school": "secondary"},
    ) == "school=secondary"
    assert source_tag(
        family("education"),
        {"amenity": "school", "name": "Pretoria Hoërskool"},
    ) == "name=Pretoria Hoërskool"


def test_service_tags_preserve_informative_classification_metadata() -> None:
    tags = {
        "name": "Battery campus",
        "official_name": "Regional battery energy storage system",
        "power": "generator",
        "generator:source": "solar;battery",
        "operator": "Example Grid",
        "source": "survey",
        "created_by": "editor",
    }
    assert service_tags(tags) == {
        "name": "Battery campus",
        "official_name": "Regional battery energy storage system",
        "operator": "Example Grid",
        "power": "generator",
        "generator:source": "solar;battery",
    }
