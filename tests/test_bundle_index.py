from __future__ import annotations

"""Invariants du catalogue exports/bundles/bundle_index.json.

Détecte les incohérences observées le 2026-07-11 :
- JSON invalide (virgule finale) ;
- bundle présent sur disque mais absent de l'index (ex. Canberra) ;
- valeurs divergentes entre l'index et le manifest (ex. heightmapSizeKm
  de Paris à 57.344 au lieu de 14.336) ;
- ordre de tri différent de celui produit par write_bundle_index.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from write_cs2_bundle_manifest import build_bundle_index_entry  # noqa: E402

BUNDLE_ROOT = ROOT / "exports" / "bundles"
INDEX_PATH = BUNDLE_ROOT / "bundle_index.json"


def _load_index() -> dict:
    assert INDEX_PATH.exists(), f"Index absent : {INDEX_PATH}"
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - message explicite
        pytest.fail(f"bundle_index.json est un JSON invalide : {exc}")


def _bundle_dirs_on_disk() -> dict[str, Path]:
    return {
        p.name: p
        for p in sorted(BUNDLE_ROOT.iterdir())
        if p.is_dir() and (p / "manifest.json").exists()
    }


def test_index_is_valid_json_with_expected_schema() -> None:
    data = _load_index()
    assert data.get("schemaVersion") == 1
    assert data.get("version") == 1
    assert isinstance(data.get("bundles"), list)


def test_index_has_an_explicit_existing_active_bundle() -> None:
    data = _load_index()
    active_bundle_id = data.get("activeBundleId")
    indexed = {entry["id"] for entry in data["bundles"]}

    assert active_bundle_id, "activeBundleId absent de bundle_index.json"
    assert active_bundle_id in indexed, (
        f"activeBundleId={active_bundle_id!r} ne correspond à aucune entrée de l'index"
    )


def test_every_bundle_on_disk_is_indexed_and_vice_versa() -> None:
    data = _load_index()
    indexed = {entry["id"] for entry in data["bundles"]}
    on_disk = set(_bundle_dirs_on_disk())

    missing_from_index = on_disk - indexed
    orphans_in_index = indexed - on_disk

    assert not missing_from_index, (
        f"Bundles sur disque absents de l'index : {sorted(missing_from_index)}. "
        "Règle du projet : bundle_index.json doit être mis à jour à chaque création de bundle."
    )
    assert not orphans_in_index, (
        f"Entrées d'index sans bundle sur disque : {sorted(orphans_in_index)}"
    )


def test_index_entries_match_their_manifests() -> None:
    data = _load_index()
    dirs = _bundle_dirs_on_disk()

    for entry in data["bundles"]:
        bundle_id = entry["id"]
        manifest = json.loads(
            (dirs[bundle_id] / "manifest.json").read_text(encoding="utf-8")
        )
        expected = build_bundle_index_entry(manifest)
        assert entry == expected, (
            f"Entrée d'index incohérente avec le manifest pour {bundle_id} :\n"
            f"  index    = {entry}\n"
            f"  attendu  = {expected}"
        )


def test_index_entries_reference_existing_paths() -> None:
    data = _load_index()
    for entry in data["bundles"]:
        manifest_path = BUNDLE_ROOT / entry["manifestPath"]
        bundle_path = BUNDLE_ROOT / entry["bundlePath"]
        assert manifest_path.is_file(), f"manifestPath introuvable : {manifest_path}"
        assert bundle_path.is_dir(), f"bundlePath introuvable : {bundle_path}"


def test_index_is_sorted_like_write_bundle_index() -> None:
    data = _load_index()
    bundles = data["bundles"]
    expected_order = sorted(
        bundles,
        key=lambda item: (
            str(item.get("country", "")),
            str(item.get("city", "")),
            str(item.get("id", "")),
        ),
    )
    assert bundles == expected_order, "Index non trié (country, city, id)"


def test_index_sizes_are_coherent() -> None:
    # Le heightmap (14,336 km) est toujours strictement plus petit que la
    # worldmap (57,344 km) — détecte l'inversion observée sur Paris.
    data = _load_index()
    for entry in data["bundles"]:
        assert entry["heightmapSizeKm"] < entry["worldmapSizeKm"], (
            f"{entry['id']} : heightmapSizeKm ({entry['heightmapSizeKm']}) doit être "
            f"< worldmapSizeKm ({entry['worldmapSizeKm']})"
        )
