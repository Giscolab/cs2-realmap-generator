import argparse
import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import shape, mapping, box
from shapely.errors import GEOSException


def parse_bbox(value: str):
    south, west, north, east = [float(x.strip()) for x in value.split(",")]
    return south, west, north, east


def read_declared_bbox(pack: Path):
    report = pack / "reports" / "extraction_report.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    return data["bbox"]


def clean_geom(geom):
    if geom is None or geom.is_empty:
        return None

    if not geom.is_valid:
        geom = geom.buffer(0)

    if geom is None or geom.is_empty:
        return None

    return geom


def clip_feature(feature, clip_box):
    geom_json = feature.get("geometry")
    if not geom_json:
        return []

    try:
        geom = shape(geom_json)
        clipped = clean_geom(geom.intersection(clip_box))
    except (GEOSException, ValueError, TypeError):
        return []

    if clipped is None:
        return []

    props = dict(feature.get("properties") or {})
    geoms = []

    if clipped.geom_type == "GeometryCollection":
        geoms = [g for g in clipped.geoms if not g.is_empty]
    elif clipped.geom_type.startswith("Multi"):
        geoms = list(clipped.geoms)
    else:
        geoms = [clipped]

    out = []
    for g in geoms:
        g = clean_geom(g)
        if g is None:
            continue

        out.append({
            "type": "Feature",
            "properties": copy.deepcopy(props),
            "geometry": mapping(g),
        })

    return out


def iter_coords(obj):
    if isinstance(obj, (list, tuple)):
        if len(obj) >= 2 and isinstance(obj[0], (int, float)) and isinstance(obj[1], (int, float)):
            yield float(obj[0]), float(obj[1])
        else:
            for item in obj:
                yield from iter_coords(item)
    elif isinstance(obj, dict):
        if "coordinates" in obj:
            yield from iter_coords(obj["coordinates"])
        else:
            for value in obj.values():
                yield from iter_coords(value)


def stats(data, south, west, north, east):
    total = 0
    outside = 0

    for lon, lat in iter_coords(data):
        if -180 <= lon <= 180 and -90 <= lat <= 90:
            total += 1
            if lon < west or lon > east or lat < south or lat > north:
                outside += 1

    return {"coords": total, "outside": outside}


def update_pack_reports(
    out_pack: Path,
    *,
    bbox: str,
    generated_at: str,
    feature_counts: dict[str, int],
    features_by_file: dict[str, list],
) -> None:
    """Réaligne les trois index et le rapport sur les fichiers clippés."""
    reports_dir = out_pack / "reports"

    layer_path = reports_dir / "layer_index.json"
    layer_index = json.loads(layer_path.read_text(encoding="utf-8"))
    for layer in layer_index.get("layers") or []:
        relative = str(layer.get("file") or "").replace("\\", "/")
        if relative not in feature_counts:
            raise RuntimeError(f"Couche indexée absente après clipping : {relative}")
        layer["count"] = feature_counts[relative]
    layer_index["generatedAt"] = generated_at
    layer_index["bbox"] = bbox
    layer_path.write_text(
        json.dumps(layer_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    roads_path = reports_dir / "roads_index.json"
    roads_index = json.loads(roads_path.read_text(encoding="utf-8"))
    for category in roads_index.get("categories") or []:
        relative = str(category.get("file") or "").replace("\\", "/")
        if relative not in feature_counts:
            raise RuntimeError(f"Catégorie routière absente après clipping : {relative}")
        category["count"] = feature_counts[relative]
    roads_index["generatedAt"] = generated_at
    roads_index["bbox"] = bbox
    roads_path.write_text(
        json.dumps(roads_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    services_path = reports_dir / "services_index.json"
    services_index = json.loads(services_path.read_text(encoding="utf-8"))
    for family in services_index.get("families") or []:
        relative = str(family.get("file") or "").replace("\\", "/")
        features = features_by_file.get(relative)
        if features is None:
            raise RuntimeError(f"Famille de services absente après clipping : {relative}")
        family["count"] = len(features)
        counts = {
            str(subcategory.get("key") or ""): 0
            for subcategory in family.get("subcategories") or []
        }
        for feature in features:
            subcategory = str((feature.get("properties") or {}).get("subcategory") or "")
            if subcategory in counts:
                counts[subcategory] += 1
        for subcategory in family.get("subcategories") or []:
            subcategory["count"] = counts[str(subcategory.get("key") or "")]
    services_index["generatedAt"] = generated_at
    services_index["bbox"] = bbox
    services_path.write_text(
        json.dumps(services_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    layers_by_name = {
        str(layer.get("name") or ""): layer
        for layer in layer_index.get("layers") or []
    }
    zone_names = (
        "residential", "commercial", "industrial", "retail",
        "parking", "office", "mixed",
    )
    source_layer_names = (
        *zone_names,
        "roads", "paths", "railways", "water_lines_clipped", "water_areas_clipped",
    )
    service_total = sum(int(family.get("count") or 0) for family in services_index.get("families") or [])
    overlay_total = sum(int(layers_by_name[name]["count"]) for name in source_layer_names)

    unique_elements = set()
    source_files = [
        str(layers_by_name[name]["file"]).replace("\\", "/")
        for name in source_layer_names
    ] + [
        str(family.get("file") or "").replace("\\", "/")
        for family in services_index.get("families") or []
    ]
    for relative in source_files:
        for feature in features_by_file.get(relative, []):
            properties = feature.get("properties") or {}
            element_id = properties.get("id")
            element_type = properties.get("osmType") or properties.get("type")
            if element_id is not None and element_type:
                unique_elements.add((str(element_type), int(element_id)))

    report_path = reports_dir / "extraction_report.json"
    extraction_report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = extraction_report.setdefault("summary", {})
    summary.update({
        "total": overlay_total,
        "overlayFeaturesWithoutServices": overlay_total,
        "legacyAllFeaturesCount": int(layers_by_name["all_features"]["count"]),
        "independentRailwayFeatureCount": int(layers_by_name["railways"]["count"]),
        "independentServiceFeatureCount": service_total,
        "allBundleFeatureCount": overlay_total + service_total,
        "uniqueOsmElementCount": len(unique_elements),
        "counts": {
            name if name not in {"water_lines_clipped", "water_areas_clipped"}
            else name.replace("_clipped", ""): int(layers_by_name[name]["count"])
            for name in source_layer_names
        },
        "serviceCounts": {
            str(family.get("key")): int(family.get("count") or 0)
            for family in services_index.get("families") or []
        },
        "clipDerived": True,
    })
    extraction_report["generatedAt"] = generated_at
    extraction_report["bbox"] = bbox
    extraction_report["outputDirectory"] = str(out_pack)
    extraction_report["layers"] = layer_index["layers"]
    report_path.write_text(
        json.dumps(extraction_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bbox", default=None, help="south,west,north,east. Default: read reports/extraction_report.json")
    args = parser.parse_args()

    src_pack = Path(args.pack).resolve()
    out_pack = Path(args.out).resolve()

    if src_pack == out_pack or src_pack in out_pack.parents or out_pack in src_pack.parents:
        raise SystemExit("[ERREUR] --pack et --out doivent être deux dossiers distincts et non imbriqués.")
    if out_pack == Path(out_pack.anchor):
        raise SystemExit("[ERREUR] Refus d'écrire ou supprimer une racine de volume.")

    bbox_str = args.bbox or read_declared_bbox(src_pack)
    south, west, north, east = parse_bbox(bbox_str)
    clip_box = box(west, south, east, north)

    if out_pack.exists():
        shutil.rmtree(out_pack)

    (out_pack / "geojson").mkdir(parents=True, exist_ok=True)
    (out_pack / "reports").mkdir(parents=True, exist_ok=True)

    if (src_pack / "reports").exists():
        shutil.copytree(src_pack / "reports", out_pack / "reports", dirs_exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generatedAt": generated_at,
        "sourcePack": str(src_pack),
        "outputPack": str(out_pack),
        "bbox": bbox_str,
        "bboxOrder": "south,west,north,east",
        "files": [],
    }

    feature_counts: dict[str, int] = {}
    features_by_file: dict[str, list] = {}

    for in_path in sorted((src_pack / "geojson").rglob("*.geojson")):
        data = json.loads(in_path.read_text(encoding="utf-8-sig"))
        before = stats(data, south, west, north, east)

        clipped_features = []
        for feature in data.get("features", []):
            clipped_features.extend(clip_feature(feature, clip_box))

        # Conserve les foreign members GeoJSON documentant le périmètre de
        # all_features.geojson (scope/includes/excludesIndependentSources).
        out_data = {
            key: copy.deepcopy(value)
            for key, value in data.items()
            if key not in {"type", "features"}
        }
        out_data.update({"type": "FeatureCollection", "features": clipped_features})

        after = stats(out_data, south, west, north, east)

        relative = in_path.relative_to(src_pack).as_posix()
        out_path = out_pack / Path(relative)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(out_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        item = {
            "file": relative,
            "featuresBefore": len(data.get("features", [])),
            "featuresAfter": len(clipped_features),
            "coordsBefore": before["coords"],
            "outsideBefore": before["outside"],
            "coordsAfter": after["coords"],
            "outsideAfter": after["outside"],
        }
        report["files"].append(item)
        feature_counts[relative] = len(clipped_features)
        features_by_file[relative] = clipped_features

        print(
            f"{relative}: outside {before['outside']} -> {after['outside']} "
            f"| features {item['featuresBefore']} -> {item['featuresAfter']}"
        )

    update_pack_reports(
        out_pack,
        bbox=bbox_str,
        generated_at=generated_at,
        feature_counts=feature_counts,
        features_by_file=features_by_file,
    )

    (out_pack / "reports" / "true_clip_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("OK true clip")
    print(f"Source : {src_pack}")
    print(f"Output : {out_pack}")
    print(f"BBOX   : {bbox_str}")


if __name__ == "__main__":
    main()
