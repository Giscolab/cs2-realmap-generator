from __future__ import annotations

"""Validation exhaustive d'un bundle CS2 RealMap.

Le manifeste référence les index de couches. Ce validateur suit ensuite chaque
référence de ces index et vérifie que l'intégralité des GeoJSON produites est
présente, lisible et comptée correctement. Une catégorie à zéro reste valide :
son fichier doit exister et contenir une FeatureCollection vide.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from road_categories import ROAD_CATEGORIES  # noqa: E402
from service_families import SERVICE_FAMILIES  # noqa: E402


class BundleValidationError(ValueError):
    """Le bundle n'honore pas le contrat complet attendu par le HUD."""


def _forbidden_visual_property_key(value: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", str(value).casefold())
    return (
        normalized == "roadimport"
        or normalized.startswith("import")
        or normalized.startswith("prefab")
        or normalized.startswith("spawn")
    )


def _validate_visual_only_properties(value: object, location: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _forbidden_visual_property_key(key):
                raise BundleValidationError(
                    f"Propriété interdite par le contrat visuel uniquement : {location}.{key}"
                )
            _validate_visual_only_properties(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_visual_only_properties(nested, f"{location}[{index}]")


def _coordinate(value: object, location: str) -> None:
    if not isinstance(value, list) or len(value) < 2:
        raise BundleValidationError(f"Coordonnée invalide : {location}")
    lon, lat = value[0], value[1]
    if (
        not isinstance(lon, (int, float))
        or isinstance(lon, bool)
        or not isinstance(lat, (int, float))
        or isinstance(lat, bool)
        or not math.isfinite(float(lon))
        or not math.isfinite(float(lat))
        or not -180 <= float(lon) <= 180
        or not -90 <= float(lat) <= 90
    ):
        raise BundleValidationError(f"Coordonnée hors domaine GeoJSON : {location}")


def _line_coordinates(value: object, location: str, *, closed: bool = False) -> None:
    minimum = 4 if closed else 2
    if not isinstance(value, list) or len(value) < minimum:
        raise BundleValidationError(f"Ligne GeoJSON trop courte : {location}")
    for index, coordinate in enumerate(value):
        _coordinate(coordinate, f"{location}[{index}]")
    if closed and value[0][:2] != value[-1][:2]:
        raise BundleValidationError(f"Anneau Polygon non fermé : {location}")


def _polygon_coordinates(value: object, location: str) -> None:
    if not isinstance(value, list) or not value:
        raise BundleValidationError(f"Polygon sans anneau : {location}")
    for index, ring in enumerate(value):
        _line_coordinates(ring, f"{location}[{index}]", closed=True)


def _validate_geometry(geometry: object, location: str, expected_geometry: str | None) -> None:
    if not isinstance(geometry, dict):
        raise BundleValidationError(f"Geometry absente ou invalide : {location}")
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    allowed_by_contract = {
        "Point": {"Point"},
        "LineString": {"LineString"},
        "Polygon": {"Polygon", "MultiPolygon"},
        "Mixed": {"Point", "LineString", "Polygon", "MultiPolygon"},
        None: {"Point", "LineString", "Polygon", "MultiPolygon"},
    }
    allowed = allowed_by_contract.get(expected_geometry)
    if allowed is None:
        raise BundleValidationError(f"geometryType d'index inconnu : {expected_geometry!r}")
    if geometry_type not in allowed:
        raise BundleValidationError(
            f"Type de géométrie incohérent dans {location} : {geometry_type!r}, attendu {expected_geometry!r}"
        )
    if geometry_type == "Point":
        _coordinate(coordinates, f"{location}.coordinates")
    elif geometry_type == "LineString":
        _line_coordinates(coordinates, f"{location}.coordinates")
    elif geometry_type == "Polygon":
        _polygon_coordinates(coordinates, f"{location}.coordinates")
    elif geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise BundleValidationError(f"MultiPolygon vide : {location}")
        for index, polygon in enumerate(coordinates):
            _polygon_coordinates(polygon, f"{location}.coordinates[{index}]")


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleValidationError(f"{label} manquant : {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleValidationError(f"{label} illisible : {path} ({exc})") from exc


def _safe_relative_path(value: object, label: str) -> Path:
    normalized = str(value or "").replace("\\", "/").strip()
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or pure.is_absolute()
        or ".." in pure.parts
        or (pure.parts and ":" in pure.parts[0])
    ):
        raise BundleValidationError(f"{label} n'est pas un chemin relatif sûr : {value!r}")
    return Path(*pure.parts)


def _manifest_bundle_relative(value: object, manifest: dict, label: str) -> Path:
    """Convertit un chemin repo du manifeste en chemin relatif au bundle."""
    normalized = str(value or "").replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]

    bundle_prefix = str(manifest.get("paths", {}).get("bundleDir") or "").replace("\\", "/")
    if bundle_prefix.startswith("./"):
        bundle_prefix = bundle_prefix[2:]
    bundle_prefix = bundle_prefix.rstrip("/")

    if not bundle_prefix or not (
        normalized == bundle_prefix or normalized.startswith(bundle_prefix + "/")
    ):
        raise BundleValidationError(
            f"{label} sort du bundle déclaré {bundle_prefix!r} : {value!r}"
        )

    relative = normalized[len(bundle_prefix):].lstrip("/")
    return _safe_relative_path(relative or ".", label)


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise BundleValidationError(f"{label} manquant : {path}")
    if path.stat().st_size <= 0:
        raise BundleValidationError(f"{label} vide : {path}")


def _validate_geojson(
    path: Path,
    expected_count: int,
    label: str,
    expected_geometry: str | None = None,
) -> dict:
    data = _load_json(path, label)
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise BundleValidationError(f"{label} n'est pas une FeatureCollection : {path}")
    features = data.get("features")
    if not isinstance(features, list):
        raise BundleValidationError(f"{label}.features n'est pas une liste : {path}")
    if len(features) != expected_count:
        raise BundleValidationError(
            f"Comptage incohérent pour {label} : index={expected_count}, fichier={len(features)}"
        )
    for position, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise BundleValidationError(f"Feature #{position} invalide dans {label}")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise BundleValidationError(
                f"Feature #{position} sans objet properties dans {label}"
            )
        _validate_geometry(
            feature.get("geometry"),
            f"{label}.features[{position}].geometry",
            expected_geometry,
        )
        _validate_visual_only_properties(properties, f"{label}.features[{position}].properties")
    return data


def _indexed_file(
    pack_dir: Path,
    value: object,
    expected_count: object,
    label: str,
    expected_geometry: str | None = None,
) -> tuple[str, dict]:
    relative = _safe_relative_path(value, f"{label}.file")
    try:
        count = int(expected_count)
    except (TypeError, ValueError) as exc:
        raise BundleValidationError(f"{label}.count invalide : {expected_count!r}") from exc
    if count < 0:
        raise BundleValidationError(f"{label}.count négatif : {count}")
    path = pack_dir / relative
    data = _validate_geojson(path, count, label, expected_geometry)
    return relative.as_posix(), data


def _validate_layer_index(pack_dir: Path, path: Path) -> tuple[dict, dict[str, dict], set[str]]:
    data = _load_json(path, "layer_index.json")
    layers = data.get("layers") if isinstance(data, dict) else None
    if not isinstance(layers, list):
        raise BundleValidationError("layer_index.json.layers doit être une liste")

    by_name: dict[str, dict] = {}
    referenced: set[str] = set()
    for position, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise BundleValidationError(f"Couche #{position} invalide dans layer_index.json")
        name = str(layer.get("name") or "").strip()
        if not name or name in by_name:
            raise BundleValidationError(f"Nom de couche vide ou dupliqué : {name!r}")
        relative, _ = _indexed_file(
            pack_dir,
            layer.get("file"),
            layer.get("count"),
            f"couche {name}",
            str(layer.get("geometryType") or "") or None,
        )
        if relative in referenced:
            raise BundleValidationError(f"GeoJSON référencé plusieurs fois : {relative}")
        layer["_relativeFile"] = relative
        by_name[name] = layer
        referenced.add(relative)

    required_layers = {
        "residential", "commercial", "industrial", "retail", "parking",
        "office", "mixed", "zoning_polygons", "roads", "roads_major_clipped",
        "roads_driveable_clipped", "paths", "railways", "water_lines_clipped",
        "water_areas_clipped", "all_features",
    }
    required_layers.update(
        f"roads_{category['key']}"
        for category in ROAD_CATEGORIES
        if category["key"] != "pathway"
    )
    missing = sorted(required_layers - by_name.keys())
    if missing:
        raise BundleValidationError(
            "Couches absentes de layer_index.json : " + ", ".join(missing)
        )

    zoning_total = sum(
        int(by_name[name]["count"])
        for name in ("residential", "commercial", "industrial", "retail", "parking", "office", "mixed")
    )
    if int(by_name["zoning_polygons"]["count"]) != zoning_total:
        raise BundleValidationError(
            "zoning_polygons.count ne correspond pas à la somme des sept couches de zonage"
        )

    all_features_contract = (data.get("contracts") or {}).get("all_features")
    expected_includes = {
        "residential", "commercial", "industrial", "retail", "parking",
        "office", "mixed", "roads", "paths", "water_lines", "water_areas",
    }
    if (
        not isinstance(all_features_contract, dict)
        or all_features_contract.get("scope") != "legacy-base-overlays"
        or set(all_features_contract.get("includes") or []) != expected_includes
        or set(all_features_contract.get("excludesIndependentSources") or [])
        != {"railways", "services/*"}
    ):
        raise BundleValidationError(
            "layer_index.contracts.all_features ne décrit pas explicitement son périmètre sans duplication"
        )
    all_features_data = _load_json(
        pack_dir / Path(by_name["all_features"]["_relativeFile"]),
        "all_features.geojson",
    )
    if (
        all_features_data.get("scope") != all_features_contract["scope"]
        or set(all_features_data.get("includes") or []) != expected_includes
        or set(all_features_data.get("excludesIndependentSources") or [])
        != {"railways", "services/*"}
    ):
        raise BundleValidationError(
            "Les métadonnées de all_features.geojson divergent de son contrat d'index"
        )

    return data, by_name, referenced


def _validate_roads_index(pack_dir: Path, path: Path, layers: dict[str, dict]) -> set[str]:
    data = _load_json(path, "roads_index.json")
    categories = data.get("categories") if isinstance(data, dict) else None
    if not isinstance(categories, list):
        raise BundleValidationError("roads_index.json.categories doit être une liste")

    expected_keys = {category["key"] for category in ROAD_CATEGORIES}
    seen: set[str] = set()
    referenced: set[str] = set()
    total = 0
    for category in categories:
        if not isinstance(category, dict):
            raise BundleValidationError("Catégorie invalide dans roads_index.json")
        key = str(category.get("key") or "")
        if not key or key in seen:
            raise BundleValidationError(f"Catégorie routière vide ou dupliquée : {key!r}")
        relative, _ = _indexed_file(
            pack_dir,
            category.get("file"),
            category.get("count"),
            f"catégorie routière {key}",
            "LineString",
        )
        seen.add(key)
        referenced.add(relative)
        total += int(category["count"])

        layer_name = "paths" if key == "pathway" else f"roads_{key}"
        layer = layers.get(layer_name)
        if layer is None or layer.get("_relativeFile") != relative or int(layer["count"]) != int(category["count"]):
            raise BundleValidationError(
                f"La catégorie routière {key} diverge de layer_index.json"
            )

    if seen != expected_keys:
        missing = sorted(expected_keys - seen)
        extra = sorted(seen - expected_keys)
        raise BundleValidationError(
            f"Taxonomie routière incomplète (manquantes={missing}, inconnues={extra})"
        )
    expected_total = int(layers["roads"]["count"]) + int(layers["paths"]["count"])
    if total != expected_total:
        raise BundleValidationError(
            f"Somme des catégories routières incohérente : {total} != {expected_total}"
        )
    return referenced


def _validate_services_index(pack_dir: Path, path: Path) -> tuple[set[str], dict[str, int]]:
    data = _load_json(path, "services_index.json")
    families = data.get("families") if isinstance(data, dict) else None
    if not isinstance(families, list):
        raise BundleValidationError("services_index.json.families doit être une liste")

    expected = {family["key"]: family for family in SERVICE_FAMILIES}
    seen: set[str] = set()
    referenced: set[str] = set()
    for family_entry in families:
        if not isinstance(family_entry, dict):
            raise BundleValidationError("Famille invalide dans services_index.json")
        key = str(family_entry.get("key") or "")
        if not key or key in seen:
            raise BundleValidationError(f"Famille de services vide ou dupliquée : {key!r}")
        family_def = expected.get(key)
        if family_def is None:
            raise BundleValidationError(f"Famille de services inconnue : {key}")

        relative, geojson = _indexed_file(
            pack_dir,
            family_entry.get("file"),
            family_entry.get("count"),
            f"famille de services {key}",
            "Point",
        )
        referenced.add(relative)
        seen.add(key)

        subcategories = family_entry.get("subcategories")
        if not isinstance(subcategories, list):
            raise BundleValidationError(f"Sous-catégories absentes pour la famille {key}")
        expected_subs = {sub["key"] for sub in family_def["subcategories"]}
        sub_counts: dict[str, int] = {}
        for sub in subcategories:
            if not isinstance(sub, dict):
                raise BundleValidationError(f"Sous-catégorie invalide pour la famille {key}")
            sub_key = str(sub.get("key") or "")
            if not sub_key or sub_key in sub_counts:
                raise BundleValidationError(f"Sous-catégorie vide ou dupliquée : {key}/{sub_key}")
            try:
                sub_counts[sub_key] = int(sub.get("count"))
            except (TypeError, ValueError) as exc:
                raise BundleValidationError(f"Comptage invalide : {key}/{sub_key}") from exc
        if set(sub_counts) != expected_subs:
            raise BundleValidationError(
                f"Sous-catégories incomplètes pour {key} : attendues={sorted(expected_subs)}, reçues={sorted(sub_counts)}"
            )
        if sum(sub_counts.values()) != int(family_entry["count"]):
            raise BundleValidationError(
                f"Somme des sous-catégories incohérente pour {key}"
            )

        feature_counts = {sub_key: 0 for sub_key in expected_subs}
        for feature in geojson["features"]:
            properties = feature.get("properties") if isinstance(feature, dict) else None
            sub_key = str((properties or {}).get("subcategory") or "")
            if (properties or {}).get("family") != key or sub_key not in feature_counts:
                raise BundleValidationError(
                    f"Feature de service mal classée dans {relative} : famille={((properties or {}).get('family'))!r}, sous-catégorie={sub_key!r}"
                )
            feature_counts[sub_key] += 1
        if feature_counts != sub_counts:
            raise BundleValidationError(
                f"Comptages de features par sous-catégorie incohérents pour {key}"
            )

    if seen != set(expected):
        raise BundleValidationError(
            "Familles de services absentes : " + ", ".join(sorted(set(expected) - seen))
        )
    return referenced, {
        str(family["key"]): int(family["count"])
        for family in families
    }


def _validate_extraction_report(
    path: Path,
    layer_index: dict,
    layers: dict[str, dict],
    service_counts: dict[str, int],
) -> None:
    report = _load_json(path, "extraction_report.json")
    report_layers = report.get("layers") if isinstance(report, dict) else None
    if report_layers != [
        {key: value for key, value in layer.items() if key != "_relativeFile"}
        for layer in layer_index["layers"]
    ]:
        raise BundleValidationError(
            "extraction_report.json.layers diverge de layer_index.json"
        )

    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise BundleValidationError("extraction_report.json.summary absent")
    source_layers = {
        "residential": "residential",
        "commercial": "commercial",
        "industrial": "industrial",
        "retail": "retail",
        "parking": "parking",
        "office": "office",
        "mixed": "mixed",
        "roads": "roads",
        "paths": "paths",
        "railways": "railways",
        "water_lines": "water_lines_clipped",
        "water_areas": "water_areas_clipped",
    }
    expected_counts = {
        source: int(layers[layer]["count"])
        for source, layer in source_layers.items()
    }
    if summary.get("counts") != expected_counts:
        raise BundleValidationError(
            "extraction_report.summary.counts diverge des couches sources"
        )
    overlay_total = sum(expected_counts.values())
    service_total = sum(service_counts.values())
    expected_scalars = {
        "total": overlay_total,
        "overlayFeaturesWithoutServices": overlay_total,
        "legacyAllFeaturesCount": int(layers["all_features"]["count"]),
        "independentRailwayFeatureCount": int(layers["railways"]["count"]),
        "independentServiceFeatureCount": service_total,
        "allBundleFeatureCount": overlay_total + service_total,
    }
    for key, expected in expected_scalars.items():
        if summary.get(key) != expected:
            raise BundleValidationError(
                f"extraction_report.summary.{key} incohérent : {summary.get(key)!r} != {expected}"
            )
    if summary.get("serviceCounts") != service_counts:
        raise BundleValidationError(
            "extraction_report.summary.serviceCounts diverge de services_index.json"
        )
    unique_osm = summary.get("uniqueOsmElementCount")
    if (
        not isinstance(unique_osm, int)
        or isinstance(unique_osm, bool)
        or unique_osm < 0
        or unique_osm > overlay_total + service_total
    ):
        raise BundleValidationError(
            "extraction_report.summary.uniqueOsmElementCount est invalide"
        )


def validate_bundle_directory(
    bundle_dir: Path,
    *,
    bundle_index_path: Path | None = None,
    require_active: bool = False,
) -> dict:
    """Valide toutes les couches, rapports, PNG et pointeurs d'un bundle."""
    bundle_dir = Path(bundle_dir).resolve()
    manifest_path = bundle_dir / "manifest.json"
    manifest = _load_json(manifest_path, "manifest.json")
    if not isinstance(manifest, dict):
        raise BundleValidationError("manifest.json doit être un objet JSON")

    bundle_id = str((manifest.get("bundle") or {}).get("id") or "")
    if not bundle_id or bundle_id != bundle_dir.name:
        raise BundleValidationError(
            f"Identité de bundle incohérente : manifeste={bundle_id!r}, dossier={bundle_dir.name!r}"
        )
    timeline = manifest.get("timelineMod") or {}
    if timeline.get("activeBundleId") != bundle_id:
        raise BundleValidationError("timelineMod.activeBundleId diverge de bundle.id")
    if timeline.get("useBundleIndex") is not True:
        raise BundleValidationError("timelineMod.useBundleIndex doit être true")

    paths = manifest.get("paths") or {}
    geojson_contract = manifest.get("geojson") or {}
    for key in ("worldmapPng", "heightmapPng", "geojsonDir", "timelineConfig"):
        if key not in paths:
            raise BundleValidationError(f"manifest.paths.{key} absent")
    for key in (
        "allFeatures", "zoningPolygons", "roads", "roadsMajor", "roadsDriveable",
        "paths", "railways", "waterLines", "waterAreas", "layerIndex",
        "extractionReport", "roadsIndex", "servicesIndex", "services",
    ):
        if key not in geojson_contract:
            raise BundleValidationError(f"manifest.geojson.{key} absent")

    for key in ("worldmapPng", "heightmapPng"):
        relative = _manifest_bundle_relative(paths[key], manifest, f"paths.{key}")
        _require_file(bundle_dir / relative, key)

    timeline_relative = _manifest_bundle_relative(paths["timelineConfig"], manifest, "paths.timelineConfig")
    timeline_config = _load_json(bundle_dir / timeline_relative, "timeline_config.json")
    if not isinstance(timeline_config, dict) or timeline_config.get("activeBundleId") != bundle_id:
        raise BundleValidationError("timeline_config.json ne sélectionne pas ce bundle")

    pack_relative = _manifest_bundle_relative(paths["geojsonDir"], manifest, "paths.geojsonDir")
    pack_dir = bundle_dir / pack_relative
    if not pack_dir.is_dir():
        raise BundleValidationError(f"geojson_pack manquant : {pack_dir}")

    def contract_path(key: str) -> Path:
        relative = _manifest_bundle_relative(geojson_contract[key], manifest, f"geojson.{key}")
        path = bundle_dir / relative
        _require_file(path, f"geojson.{key}")
        return path

    layer_index_path = contract_path("layerIndex")
    roads_index_path = contract_path("roadsIndex")
    services_index_path = contract_path("servicesIndex")
    extraction_report_path = contract_path("extractionReport")

    layer_index, layers, layer_files = _validate_layer_index(pack_dir, layer_index_path)
    road_files = _validate_roads_index(pack_dir, roads_index_path, layers)
    service_files, service_counts = _validate_services_index(pack_dir, services_index_path)
    _validate_extraction_report(
        extraction_report_path,
        layer_index,
        layers,
        service_counts,
    )

    # Le manifeste doit pointer exactement vers les sources canoniques déjà
    # présentes dans les index, notamment railways.geojson et les 9 services.
    contract_layer_names = {
        "allFeatures": "all_features",
        "zoningPolygons": "zoning_polygons",
        "roads": "roads",
        "roadsMajor": "roads_major_clipped",
        "roadsDriveable": "roads_driveable_clipped",
        "paths": "paths",
        "railways": "railways",
        "waterLines": "water_lines_clipped",
        "waterAreas": "water_areas_clipped",
    }
    for contract_key, layer_name in contract_layer_names.items():
        contract_file = _manifest_bundle_relative(
            geojson_contract[contract_key], manifest, f"geojson.{contract_key}"
        )
        indexed_file = pack_relative / Path(layers[layer_name]["_relativeFile"])
        if contract_file.as_posix() != indexed_file.as_posix():
            raise BundleValidationError(
                f"manifest.geojson.{contract_key} diverge de layer_index.json"
            )

    service_contract = geojson_contract.get("services")
    if not isinstance(service_contract, dict):
        raise BundleValidationError("manifest.geojson.services doit être un objet")
    if set(service_contract) != {family["key"] for family in SERVICE_FAMILIES}:
        raise BundleValidationError("manifest.geojson.services ne contient pas les 9 familles exactes")
    for key, value in service_contract.items():
        contract_file = _manifest_bundle_relative(value, manifest, f"geojson.services.{key}")
        expected = pack_relative / Path(f"geojson/services/{key}.geojson")
        if contract_file.as_posix() != expected.as_posix():
            raise BundleValidationError(f"Chemin de service non canonique : {key}")

    # Aucun GeoJSON produit ne doit rester invisible parce qu'il n'est référencé
    # par aucun index transitivement relié au manifeste.
    actual_geojson = {
        path.relative_to(pack_dir).as_posix()
        for path in (pack_dir / "geojson").rglob("*.geojson")
        if path.is_file()
    }
    indexed_geojson = layer_files | service_files
    if actual_geojson != indexed_geojson:
        raise BundleValidationError(
            "Inventaire GeoJSON non intégral : "
            f"non indexés={sorted(actual_geojson - indexed_geojson)}, "
            f"référencés mais absents={sorted(indexed_geojson - actual_geojson)}"
        )

    # Les entrées de routes doivent être un sous-ensemble de layer_index.
    if not road_files.issubset(layer_files):
        raise BundleValidationError("roads_index.json référence une couche absente de layer_index.json")

    if bundle_index_path is not None:
        index = _load_json(Path(bundle_index_path), "bundle_index.json")
        bundles = index.get("bundles") if isinstance(index, dict) else None
        if not isinstance(bundles, list):
            raise BundleValidationError("bundle_index.json.bundles doit être une liste")
        matching = [entry for entry in bundles if isinstance(entry, dict) and entry.get("id") == bundle_id]
        if len(matching) != 1:
            raise BundleValidationError(f"bundle_index.json doit contenir exactement une entrée {bundle_id}")
        entry = matching[0]
        if entry.get("manifestPath") != f"{bundle_id}/manifest.json" or entry.get("bundlePath") != bundle_id:
            raise BundleValidationError(f"Chemins d'index incohérents pour {bundle_id}")
        if require_active and index.get("activeBundleId") != bundle_id:
            raise BundleValidationError(
                f"activeBundleId={index.get('activeBundleId')!r} diverge de {bundle_id!r}"
            )

    return {
        "bundleId": bundle_id,
        "layerCount": len(layers),
        "geojsonFileCount": len(actual_geojson),
        "serviceFamilyCount": len(SERVICE_FAMILIES),
        # Aucun « total features » ambigu : layer_index contient volontairement
        # des agrégats et sous-ensembles (zoning_polygons, all_features, routes).
        "indexedLayerCounts": {
            name: int(layer["count"])
            for name, layer in layers.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valide l'intégralité d'un bundle CS2 RealMap et ses index."
    )
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--bundle-index", type=Path, default=None)
    parser.add_argument("--require-active", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_bundle_directory(
            args.bundle,
            bundle_index_path=args.bundle_index,
            require_active=args.require_active,
        )
    except BundleValidationError as exc:
        print(f"[ERREUR] Bundle incomplet : {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] Bundle intégral validé : "
        f"{report['bundleId']} — {report['layerCount']} couches indexées, "
        f"{report['geojsonFileCount']} GeoJSON, "
        f"{report['serviceFamilyCount']} familles de services."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
