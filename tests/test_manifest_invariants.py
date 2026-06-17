from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from write_cs2_bundle_manifest import (  # noqa: E402
    build_manifest,
    validate_manifest_invariants,
)


def make_args(**overrides) -> SimpleNamespace:
    """Args minimaux pour build_manifest (mêmes valeurs que les défauts CLI)."""
    base = dict(
        center_lon=2.352448,
        center_lat=48.857487,
        city="Paris",
        country="France",
        country_code="fr",
        bundle_id=None,
        worldmap_size_km=57.344,
        heightmap_size_km=14.336,
        pixels=4096,
        tiles=4,
        tile_overlap_px=128,
        valid_min_elev=-200,
        valid_max_elev=5000,
        heightmap_normalization="nonta-manual",
        cs2_base_level=1.0,
        below_sea_reserve_meters=511.7,
        cs2_elevation_scale=4096.0,
        cs2_vertical_scale=1.0,
        recommended_cs2_water_level=None,
        world_bbox=None,
        heightmap_bbox=None,
        exports_root="exports",
        bundle_root="exports/bundles",
        bundle_index=None,
        png_dir=None,
        geojson_dir=None,
        out=None,
        timeline_config_out=None,
        legacy_flat_output=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_manifest_produces_distinct_bboxes() -> None:
    manifest = build_manifest(make_args())
    assert manifest["worldMap"]["bbox"] != manifest["heightmap"]["bbox"]


def test_build_manifest_png_names_carry_correct_sizes() -> None:
    manifest = build_manifest(make_args())
    assert manifest["paths"]["worldmapPng"].endswith("_57.344.png")
    assert manifest["paths"]["heightmapPng"].endswith("_14.336.png")


def test_valid_manifest_passes_invariants() -> None:
    manifest = build_manifest(make_args())
    # Ne doit pas lever.
    validate_manifest_invariants(manifest)


def test_identical_bboxes_with_different_sizes_is_rejected() -> None:
    # Reproduit le bug observé (manifeste Paris) : bbox heightmap = bbox worldmap.
    manifest = build_manifest(make_args())
    manifest["heightmap"]["bbox"] = manifest["worldMap"]["bbox"]
    with pytest.raises(SystemExit, match="bbox"):
        validate_manifest_invariants(manifest)


def test_heightmap_png_with_worldmap_size_is_rejected() -> None:
    manifest = build_manifest(make_args())
    manifest["paths"]["heightmapPng"] = manifest["paths"]["heightmapPng"].replace(
        "_14.336.png", "_57.344.png"
    )
    with pytest.raises(SystemExit, match="heightmap PNG"):
        validate_manifest_invariants(manifest)


def test_misordered_bbox_is_rejected() -> None:
    manifest = build_manifest(make_args())
    south, west, north, east = manifest["worldMap"]["bbox"].split(",")
    # Inverse sud/nord -> sud > nord.
    manifest["worldMap"]["bbox"] = ",".join([north, west, south, east])
    with pytest.raises(SystemExit, match="mal ordonnée"):
        validate_manifest_invariants(manifest)


def test_bbox_span_inconsistent_with_size_is_rejected() -> None:
    # sizeKm annoncée incohérente avec l'étendue réelle de la bbox (~57 km).
    manifest = build_manifest(make_args())
    manifest["worldMap"]["sizeKm"] = 99.0  # bbox inchangée (~57 km)
    with pytest.raises(SystemExit, match="incohérente avec sizeKm"):
        validate_manifest_invariants(manifest)
