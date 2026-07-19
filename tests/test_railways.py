from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extract_zoning import write_split_layers_pack  # noqa: E402
from railways import (  # noqa: E402
    ACTIVE_RAILWAY_TYPES,
    RAILWAY_SERVICE_TYPES,
    build_railways_query,
    is_active_railway,
    railway_item,
    railway_properties,
)


def railway_way(**tag_overrides) -> dict:
    tags = {
        "railway": "rail",
        "usage": "main",
        "tracks": "1",
        "gauge": "1435",
        "electrified": "contact_line",
        "name": "Ligne de test",
    }
    tags.update(tag_overrides)
    return {
        "type": "way",
        "id": 42,
        "tags": tags,
        "geometry": [
            {"lat": 48.85, "lon": 2.34},
            {"lat": 48.86, "lon": 2.35},
        ],
    }


def test_query_requests_only_supported_way_geometries() -> None:
    query = build_railways_query("48.8,2.3,48.9,2.4")

    assert "way[\"railway\"~\"^(rail|narrow_gauge|tram|light_rail|subway)$\"]" in query
    assert "relation[" not in query
    assert "node[" not in query
    assert "out tags geom;" in query


@pytest.mark.parametrize("railway_type", ACTIVE_RAILWAY_TYPES)
def test_supported_railway_types_are_active(railway_type: str) -> None:
    assert is_active_railway({"railway": railway_type})


@pytest.mark.parametrize(
    "tags",
    [
        {"railway": "abandoned"},
        {"railway": "disused"},
        {"railway": "proposed"},
        {"railway": "construction"},
        {"railway": "rail", "abandoned": "yes"},
        {"railway": "rail", "disused": "rail"},
        {"railway": "tram", "proposed:railway": "tram"},
        {"railway": "subway", "railway:construction": "subway"},
    ],
)
def test_inactive_lifecycle_tags_are_excluded(tags: dict) -> None:
    assert not is_active_railway(tags)


def test_explicit_negative_lifecycle_tag_keeps_active_line() -> None:
    assert is_active_railway({"railway": "rail", "disused": "no"})


def test_properties_follow_visual_overlay_contract() -> None:
    properties = railway_properties(
        railway_way(service="siding", bridge="viaduct", tunnel="no")["tags"]
    )

    assert properties == {
        "railway": "rail",
        "usage": "main",
        "service": "siding",
        "tracks": "1",
        "gauge": "1435",
        "bridge": True,
        "tunnel": False,
        "electrified": "contact_line",
        "name": "Ligne de test",
    }
    assert not ({"import", "prefab", "spawner", "roadImport"} & properties.keys())


@pytest.mark.parametrize("service", RAILWAY_SERVICE_TYPES)
def test_supported_service_values_are_preserved(service: str) -> None:
    assert railway_properties(railway_way(service=service)["tags"])["service"] == service


def test_unsupported_service_value_is_not_classified_as_service() -> None:
    assert railway_properties(railway_way(service="station")["tags"])["service"] is None


def test_non_way_and_short_geometry_are_rejected() -> None:
    assert railway_item({**railway_way(), "type": "relation"}) is None
    assert railway_item({**railway_way(), "geometry": [{"lat": 48.85, "lon": 2.34}]}) is None


def test_pack_writes_one_independent_linestring_source(tmp_path: Path) -> None:
    item = railway_item(railway_way(service="yard", tunnel="yes"))
    assert item is not None

    write_split_layers_pack(
        output={"railways": [item]},
        city="Test",
        bbox="48.8,2.3,48.9,2.4",
        out_dir=tmp_path,
        generated_at="2026-07-19T00:00:00+00:00",
        report={"counts": {"railways": 1}},
    )

    railway_files = list((tmp_path / "geojson").glob("railway*.geojson"))
    assert railway_files == [tmp_path / "geojson" / "railways.geojson"]

    railways = json.loads(railway_files[0].read_text(encoding="utf-8"))
    assert railways["type"] == "FeatureCollection"
    assert len(railways["features"]) == 1
    feature = railways["features"][0]
    assert feature["geometry"] == {
        "type": "LineString",
        "coordinates": [[2.34, 48.85], [2.35, 48.86]],
    }
    assert feature["properties"]["railway"] == "rail"
    assert feature["properties"]["id"] == 42
    assert feature["properties"]["service"] == "yard"
    assert feature["properties"]["tunnel"] is True

    all_features = json.loads(
        (tmp_path / "geojson" / "all_features.geojson").read_text(encoding="utf-8")
    )
    assert all_features["features"] == []

    layer_index = json.loads(
        (tmp_path / "reports" / "layer_index.json").read_text(encoding="utf-8")
    )
    railway_layers = [layer for layer in layer_index["layers"] if layer["name"] == "railways"]
    assert railway_layers == [{
        "name": "railways",
        "file": "geojson/railways.geojson",
        "geometryType": "LineString",
        "count": 1,
    }]
