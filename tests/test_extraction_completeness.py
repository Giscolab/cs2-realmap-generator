from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from classifiers import classify_path  # noqa: E402
from extract_zoning import (  # noqa: E402
    extract_polygon_parts,
    is_driveable_road,
    parse_building_levels,
    polygon_feature,
)
from overpass_client import build_paths_query, build_roads_query  # noqa: E402


def test_road_query_keeps_all_active_fallbacks_without_duplicating_paths() -> None:
    query = build_roads_query("0,0,1,1")

    assert 'way["highway"]' in query
    assert '["highway"!~"^(pedestrian|footway|path|steps|cycleway|bridleway|corridor|platform)$"]' in query
    assert "road|track" not in query  # aucune liste blanche pouvant les oublier
    assert 'construction|disused|planned|proposed|razed' in query
    assert is_driveable_road({"tags": {"highway": "track"}})
    assert is_driveable_road({"tags": {"highway": "emergency_bay"}})


def test_path_query_and_classifier_cover_the_complete_hud_taxonomy() -> None:
    query = build_paths_query("0,0,1,1")

    for highway in ("footway", "path", "steps", "pedestrian", "cycleway", "bridleway", "corridor", "platform"):
        assert highway in query
        assert classify_path({"highway": highway})["confidence"] == "direct"


def _member(role: str, coordinates: list[tuple[float, float]]) -> dict:
    return {
        "type": "way",
        "role": role,
        "geometry": [
            {"lat": latitude, "lon": longitude}
            for latitude, longitude in coordinates
        ],
    }


def test_relation_keeps_all_outer_parts_and_inner_holes() -> None:
    relation = {
        "type": "relation",
        "id": 99,
        "members": [
            _member("outer", [(0, 0), (0, 4)]),
            _member("outer", [(0, 4), (4, 4)]),
            _member("outer", [(4, 4), (4, 0)]),
            _member("outer", [(4, 0), (0, 0)]),
            _member("outer", [(10, 10), (10, 11), (11, 11), (11, 10), (10, 10)]),
            _member("inner", [(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)]),
        ],
    }

    parts = extract_polygon_parts(relation)
    feature = polygon_feature({
        "id": 99,
        "coords": parts[0]["outer"],
        "polygonParts": parts,
    })

    assert len(parts) == 2
    assert [len(part["inners"]) for part in parts] == [1, 0]
    assert feature is not None
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert len(feature["geometry"]["coordinates"]) == 2
    assert len(feature["geometry"]["coordinates"][0]) == 2
    assert "polygonParts" not in feature["properties"]


def test_building_levels_parser_keeps_numeric_density_information() -> None:
    assert parse_building_levels("4") == 4
    assert parse_building_levels("3,5") == 3
    assert parse_building_levels("unknown") == 0
