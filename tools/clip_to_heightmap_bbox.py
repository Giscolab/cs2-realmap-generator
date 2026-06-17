import csv
import json
import math
from pathlib import Path

from shapely.geometry import shape, mapping, box
from shapely.errors import GEOSException

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "analysis_zoning_data" / "exports"
OUT_DIR = ROOT / "analysis_zoning_data" / "clipped"
OUT_DIR.mkdir(exist_ok=True)

# BBOX heightmap utilisée par extract_zoning.py
SOUTH = 33.584339
WEST = -117.869246
NORTH = 33.756051
EAST = -117.662922

CLIP_BOX = box(WEST, SOUTH, EAST, NORTH)

def iter_coords(obj):
    if isinstance(obj, (list, tuple)):
        if (
            len(obj) >= 2
            and isinstance(obj[0], (int, float))
            and isinstance(obj[1], (int, float))
        ):
            yield float(obj[0]), float(obj[1])
        else:
            for item in obj:
                yield from iter_coords(item)

def bbox_from_features(features):
    lons = []
    lats = []

    for feature in features:
        geom = feature.get("geometry")
        if not geom:
            continue

        for lon, lat in iter_coords(geom.get("coordinates")):
            lons.append(lon)
            lats.append(lat)

    if not lons:
        return None

    return {
        "minLon": min(lons),
        "maxLon": max(lons),
        "minLat": min(lats),
        "maxLat": max(lats),
    }

def bbox_meters(b):
    if not b:
        return "", ""

    center_lat = (b["minLat"] + b["maxLat"]) / 2.0
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(center_lat))

    width = (b["maxLon"] - b["minLon"]) * meters_per_deg_lon
    height = (b["maxLat"] - b["minLat"]) * meters_per_deg_lat

    return round(width, 2), round(height, 2)

def bbox_values(b):
    if not b:
        return {
            "minLon": "",
            "maxLon": "",
            "minLat": "",
            "maxLat": "",
            "centerLon": "",
            "centerLat": "",
            "width_m": "",
            "height_m": "",
        }

    width, height = bbox_meters(b)

    return {
        "minLon": b["minLon"],
        "maxLon": b["maxLon"],
        "minLat": b["minLat"],
        "maxLat": b["maxLat"],
        "centerLon": (b["minLon"] + b["maxLon"]) / 2.0,
        "centerLat": (b["minLat"] + b["maxLat"]) / 2.0,
        "width_m": width,
        "height_m": height,
    }

def clean_geometry(geom):
    if geom.is_empty:
        return None

    # Corrige certains polygones invalides si nécessaire.
    if not geom.is_valid:
        geom = geom.buffer(0)

    if geom.is_empty:
        return None

    return geom

def clip_feature(feature):
    geom_json = feature.get("geometry")
    if not geom_json:
        return None

    try:
        geom = shape(geom_json)
        clipped = geom.intersection(CLIP_BOX)
        clipped = clean_geometry(clipped)
    except (GEOSException, ValueError, TypeError):
        return None

    if clipped is None or clipped.is_empty:
        return None

    out = {
        "type": "Feature",
        "properties": dict(feature.get("properties") or {}),
        "geometry": mapping(clipped),
    }

    return out

def read_geojson(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_geojson(path, features):
    payload = {
        "type": "FeatureCollection",
        "features": features,
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

rows = []

for in_path in sorted(INPUT_DIR.glob("*.geojson")):
    data = read_geojson(in_path)
    features = data.get("features", [])

    clipped_features = []

    for feature in features:
        clipped = clip_feature(feature)
        if clipped:
            clipped_features.append(clipped)

    out_path = OUT_DIR / in_path.name
    write_geojson(out_path, clipped_features)

    before_bbox = bbox_from_features(features)
    after_bbox = bbox_from_features(clipped_features)

    row = {
        "file": in_path.name,
        "features_before": len(features),
        "features_after": len(clipped_features),
        "size_before_mb": round(in_path.stat().st_size / 1024 / 1024, 3),
        "size_after_mb": round(out_path.stat().st_size / 1024 / 1024, 3),
    }

    for prefix, b in [("before", before_bbox), ("after", after_bbox)]:
        vals = bbox_values(b)
        for key, value in vals.items():
            row[f"{prefix}_{key}"] = value

    rows.append(row)

report_path = OUT_DIR / "clip_report.csv"

with report_path.open("w", encoding="utf-8-sig", newline="") as f:
    fieldnames = [
        "file",
        "features_before",
        "features_after",
        "size_before_mb",
        "size_after_mb",

        "before_minLon",
        "before_maxLon",
        "before_minLat",
        "before_maxLat",
        "before_centerLon",
        "before_centerLat",
        "before_width_m",
        "before_height_m",

        "after_minLon",
        "after_maxLon",
        "after_minLat",
        "after_maxLat",
        "after_centerLon",
        "after_centerLat",
        "after_width_m",
        "after_height_m",
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print("OK clipping terminé")
print("BBOX:")
print(f"  south={SOUTH}")
print(f"  west={WEST}")
print(f"  north={NORTH}")
print(f"  east={EAST}")
print()
print("Rapport:")
print(report_path)
print()
print("Fichiers clippés:")
for path in sorted(OUT_DIR.glob("*.geojson")):
    print(f"- {path.name}: {path.stat().st_size / 1024 / 1024:.2f} Mo")

