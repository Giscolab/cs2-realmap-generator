from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from road_categories import (  # noqa: E402
    ROAD_CATEGORIES,
    classify_road_category,
    road_category_color,
    road_category_keys,
    road_category_label,
)


def test_seven_categories() -> None:
    assert len(ROAD_CATEGORIES) == 7
    assert road_category_keys() == [
        "highway", "large_road", "medium_road", "small_road",
        "ramp", "pathway", "gravel_road",
    ]


def test_no_highway_value_in_two_categories() -> None:
    seen = []
    for category in ROAD_CATEGORIES:
        seen.extend(category["highways"])
    assert len(seen) == len(set(seen)), "un highway OSM est mappé sur deux catégories"


@pytest.mark.parametrize("highway,expected", [
    ("motorway", "highway"),
    ("trunk", "highway"),
    ("primary", "large_road"),
    ("secondary", "medium_road"),
    ("tertiary", "small_road"),
    ("residential", "small_road"),
    ("living_street", "small_road"),
    ("motorway_link", "ramp"),
    ("primary_link", "ramp"),
    ("tertiary_link", "ramp"),
    ("pedestrian", "pathway"),
    ("footway", "pathway"),
    ("path", "pathway"),
    ("steps", "pathway"),
    ("unclassified", "gravel_road"),
    ("service", "gravel_road"),
    ("road", "gravel_road"),
    ("track", "gravel_road"),
])
def test_classify(highway, expected) -> None:
    assert classify_road_category({"highway": highway}) == expected


def test_unknown_and_empty_fall_back_to_gravel() -> None:
    assert classify_road_category({"highway": "bidule"}) == "gravel_road"
    assert classify_road_category({}) == "gravel_road"
    assert classify_road_category(None) == "gravel_road"


def test_colors_match_spec() -> None:
    assert road_category_color("highway") == "#ff4d4d"      # rouge
    assert road_category_color("large_road") == "#ff9f1c"   # orange
    assert road_category_color("medium_road") == "#ffd60a"  # jaune
    assert road_category_color("small_road") == "#ffffff"   # blanc
    assert road_category_color("ramp") == "#ff3df5"         # magenta
    assert road_category_color("pathway") == "#2ad4ff"      # cyan
    assert road_category_color("gravel_road") == "#c7d0d9"  # gris clair


def test_label_lookup() -> None:
    assert road_category_label("highway") == "Autoroute"
    assert road_category_label("inconnu") == "inconnu"
