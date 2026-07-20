from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for module_path in (SRC, TOOLS):
    if str(module_path) not in sys.path:
        sys.path.insert(0, str(module_path))

from extract_zoning import write_service_layers, write_split_layers_pack  # noqa: E402
from service_families import SERVICE_FAMILIES  # noqa: E402
from sync_citytimeline_bundle import sync_active_bundle  # noqa: E402
from validate_cs2_bundle import BundleValidationError, validate_bundle_directory  # noqa: E402
from write_cs2_bundle_manifest import (  # noqa: E402
    build_bundle_index_entry,
    build_manifest,
    write_bundle_index,
    write_json,
)


ZONE_CATEGORIES = (
    "residential", "commercial", "industrial", "retail", "parking", "office", "mixed"
)


def _args(bundle_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        center_lon=2.352448,
        center_lat=48.857487,
        city="Ville test",
        country="France",
        country_code="fr",
        bundle_id=bundle_id,
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


def make_complete_bundle(root: Path, bundle_id: str = "ville_test_fr_48.857487_2.352448") -> tuple[Path, Path]:
    manifest = build_manifest(_args(bundle_id))
    bundle_dir = root / "exports" / "bundles" / bundle_id
    pack_dir = bundle_dir / "geojson_pack"
    bbox = manifest["worldMap"]["bbox"]
    generated_at = "2026-07-20T00:00:00+00:00"

    output = {key: [] for key in ZONE_CATEGORIES}
    output.update({
        "roads": [],
        "paths": [],
        "railways": [],
        "water_lines": [],
        "water_areas": [],
    })
    write_split_layers_pack(
        output=output,
        city="Ville test",
        bbox=bbox,
        out_dir=pack_dir,
        generated_at=generated_at,
        report={
            "total": 0,
            "overlayFeaturesWithoutServices": 0,
            "legacyAllFeaturesCount": 0,
            "independentRailwayFeatureCount": 0,
            "independentServiceFeatureCount": 0,
            "allBundleFeatureCount": 0,
            "uniqueOsmElementCount": 0,
            "counts": {key: 0 for key in output},
            "serviceCounts": {family["key"]: 0 for family in SERVICE_FAMILIES},
        },
    )
    write_service_layers(
        out_dir=pack_dir,
        services={family["key"]: [] for family in SERVICE_FAMILIES},
        generated_at=generated_at,
        bbox=bbox,
    )

    png_dir = bundle_dir / "png"
    png_dir.mkdir(parents=True)
    (png_dir / Path(manifest["paths"]["worldmapPng"].replace("\\", "/")).name).write_bytes(b"PNG-world")
    (png_dir / Path(manifest["paths"]["heightmapPng"].replace("\\", "/")).name).write_bytes(b"PNG-height")

    write_json(bundle_dir / "manifest.json", manifest)
    timeline = dict(manifest["timelineMod"])
    timeline.pop("configPath", None)
    write_json(bundle_dir / "timeline_config.json", timeline)
    index_path = write_bundle_index(root, manifest)
    return bundle_dir, index_path


def test_complete_bundle_accepts_legitimate_zero_count_layers(tmp_path: Path) -> None:
    bundle_dir, index_path = make_complete_bundle(tmp_path)
    report = validate_bundle_directory(
        bundle_dir,
        bundle_index_path=index_path,
        require_active=True,
    )
    assert report["layerCount"] == 22
    assert report["geojsonFileCount"] == 31
    assert report["serviceFamilyCount"] == 9


def test_every_generated_geojson_must_be_indexed(tmp_path: Path) -> None:
    bundle_dir, _ = make_complete_bundle(tmp_path)
    extra = bundle_dir / "geojson_pack" / "geojson" / "forgotten.geojson"
    extra.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    with pytest.raises(BundleValidationError, match="non indexés"):
        validate_bundle_directory(bundle_dir)


def test_layer_count_must_match_feature_collection(tmp_path: Path) -> None:
    bundle_dir, _ = make_complete_bundle(tmp_path)
    index_path = bundle_dir / "geojson_pack" / "reports" / "layer_index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    next(layer for layer in data["layers"] if layer["name"] == "railways")["count"] = 1
    index_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BundleValidationError, match="Comptage incohérent"):
        validate_bundle_directory(bundle_dir)


def test_all_service_subcategories_are_part_of_the_contract(tmp_path: Path) -> None:
    bundle_dir, _ = make_complete_bundle(tmp_path)
    index_path = bundle_dir / "geojson_pack" / "reports" / "services_index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["families"][0]["subcategories"].pop()
    index_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BundleValidationError, match="Sous-catégories incomplètes"):
        validate_bundle_directory(bundle_dir)


def test_visual_contract_rejects_import_prefab_and_spawn_properties(tmp_path: Path) -> None:
    bundle_dir, _ = make_complete_bundle(tmp_path)
    pack = bundle_dir / "geojson_pack"
    railway_path = pack / "geojson" / "railways.geojson"
    railway = json.loads(railway_path.read_text(encoding="utf-8"))
    railway["features"].append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[2.0, 48.0], [2.1, 48.1]]},
        "properties": {"railway": "rail", "prefabHint": "interdit"},
    })
    railway_path.write_text(json.dumps(railway), encoding="utf-8")

    layer_path = pack / "reports" / "layer_index.json"
    layer_index = json.loads(layer_path.read_text(encoding="utf-8"))
    next(layer for layer in layer_index["layers"] if layer["name"] == "railways")["count"] = 1
    layer_path.write_text(json.dumps(layer_index), encoding="utf-8")
    report_path = pack / "reports" / "extraction_report.json"
    extraction_report = json.loads(report_path.read_text(encoding="utf-8"))
    next(layer for layer in extraction_report["layers"] if layer["name"] == "railways")["count"] = 1
    report_path.write_text(json.dumps(extraction_report), encoding="utf-8")

    with pytest.raises(BundleValidationError, match="contrat visuel uniquement"):
        validate_bundle_directory(bundle_dir)


def test_active_bundle_id_must_match_validated_bundle(tmp_path: Path) -> None:
    bundle_dir, index_path = make_complete_bundle(tmp_path)
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["activeBundleId"] = "ancien_bundle"
    index_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BundleValidationError, match="activeBundleId"):
        validate_bundle_directory(
            bundle_dir,
            bundle_index_path=index_path,
            require_active=True,
        )


def test_bundle_index_is_rebuilt_from_every_manifest_on_disk(tmp_path: Path) -> None:
    bundle_dir, index_path = make_complete_bundle(tmp_path)
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["bundles"][0]["recommendedWaterLevel"] = -999
    data["bundles"].append({"id": "orphan_without_manifest"})
    index_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    write_bundle_index(tmp_path, manifest)

    rebuilt = json.loads(index_path.read_text(encoding="utf-8"))
    assert rebuilt["activeBundleId"] == bundle_dir.name
    assert rebuilt["bundles"] == [build_bundle_index_entry(manifest)]


def test_sync_publishes_coherent_active_index_after_complete_bundle(tmp_path: Path) -> None:
    bundle_dir, source_index = make_complete_bundle(tmp_path / "source")
    source_root = source_index.parent
    source_data = json.loads(source_index.read_text(encoding="utf-8"))
    source_data["bundles"].append({
        "id": "bundle_non_deploye",
        "manifestPath": "bundle_non_deploye/manifest.json",
        "bundlePath": "bundle_non_deploye",
    })
    source_index.write_text(json.dumps(source_data), encoding="utf-8")
    target_root = tmp_path / "timeline" / "bundles"
    target_root.mkdir(parents=True)
    (target_root / "bundle_index.json").write_text(
        json.dumps({"activeBundleId": "paris", "bundles": []}),
        encoding="utf-8",
    )

    report = sync_active_bundle(source_root, target_root)

    assert report["bundleId"] == bundle_dir.name
    deployed_index = json.loads((target_root / "bundle_index.json").read_text(encoding="utf-8"))
    assert deployed_index["activeBundleId"] == bundle_dir.name
    assert [entry["id"] for entry in deployed_index["bundles"]] == [bundle_dir.name]
    validate_bundle_directory(
        target_root / bundle_dir.name,
        bundle_index_path=target_root / "bundle_index.json",
        require_active=True,
    )


def test_sync_is_resumable_and_removes_stale_bundle_files(tmp_path: Path) -> None:
    bundle_dir, source_index = make_complete_bundle(tmp_path / "source")
    target_root = tmp_path / "timeline" / "bundles"
    staging_bundle = target_root / f".{bundle_dir.name}.staging" / bundle_dir.name
    staging_bundle.mkdir(parents=True)
    (staging_bundle / "partial.tmp").write_text("interrompu", encoding="utf-8")

    sync_active_bundle(source_index.parent, target_root)
    stale = target_root / bundle_dir.name / "stale.tmp"
    stale.write_text("ancien", encoding="utf-8")
    sync_active_bundle(source_index.parent, target_root)

    assert not stale.exists()
    assert not (target_root / f".{bundle_dir.name}.staging").exists()


def test_invalid_source_never_replaces_existing_target_index(tmp_path: Path) -> None:
    bundle_dir, source_index = make_complete_bundle(tmp_path / "source")
    target_root = tmp_path / "timeline" / "bundles"
    target_root.mkdir(parents=True)
    old_index = b'{"activeBundleId":"paris","bundles":[]}'
    (target_root / "bundle_index.json").write_bytes(old_index)
    (bundle_dir / "geojson_pack" / "geojson" / "railways.geojson").unlink()

    with pytest.raises(BundleValidationError):
        sync_active_bundle(source_index.parent, target_root)

    assert (target_root / "bundle_index.json").read_bytes() == old_index
    assert not (target_root / bundle_dir.name).exists()


def test_sync_refuses_running_game_without_explicit_override(tmp_path: Path) -> None:
    _, source_index = make_complete_bundle(tmp_path / "source")
    target_root = tmp_path / "timeline" / "bundles"

    with pytest.raises(BundleValidationError, match="Cities2.exe"):
        sync_active_bundle(
            source_index.parent,
            target_root,
            game_running=True,
        )

    assert not target_root.exists()


def test_sync_refuses_a_concurrent_publication_lock(tmp_path: Path) -> None:
    _, source_index = make_complete_bundle(tmp_path / "source")
    target_root = tmp_path / "timeline" / "bundles"
    lock_dir = target_root / ".citytimeline-bundle-sync.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner.json").write_text('{"pid":1234}\n', encoding="utf-8")

    with pytest.raises(BundleValidationError, match="déjà en cours"):
        sync_active_bundle(
            source_index.parent,
            target_root,
            game_running=False,
        )

    assert lock_dir.is_dir()
    assert not any(
        path.is_dir() and not path.name.startswith(".")
        for path in target_root.iterdir()
    )
