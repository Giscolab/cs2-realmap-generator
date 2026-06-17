import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "visualizer" / "zoning_data.js"
OUT_DIR = ROOT / "analysis_zoning_data"
EXPORT_DIR = OUT_DIR / "exports"

OUT_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

LINE_DATASETS = {"DATA_ROADS", "DATA_PATHS"}

def find_matching_json(text, start):
    opener = text[start]
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    raise ValueError("Bloc JSON non terminé")

def load_datasets(path):
    text = path.read_text(encoding="utf-8-sig")
    datasets = {}

    pattern = re.compile(r"const\s+(DATA_[A-Z0-9_]+)\s*=\s*", re.M)

    for match in pattern.finditer(text):
        name = match.group(1)
        i = match.end()

        while i < len(text) and text[i].isspace():
            i += 1

        if i >= len(text) or text[i] not in "[{":
            continue

        payload = find_matching_json(text, i)
        datasets[name] = json.loads(payload)

    return datasets

def is_coord_pair(value):
    return (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    )

def extract_pairs(coords):
    pairs = []

    if not isinstance(coords, list):
        return pairs

    for item in coords:
        if is_coord_pair(item):
            lat = float(item[0])
            lon = float(item[1])
            pairs.append((lat, lon))
        elif isinstance(item, list):
            pairs.extend(extract_pairs(item))

    return pairs

def bbox_meters(min_lon, min_lat, max_lon, max_lat):
    center_lat = (min_lat + max_lat) / 2.0
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(center_lat))
    return (
        (max_lon - min_lon) * meters_per_deg_lon,
        (max_lat - min_lat) * meters_per_deg_lat,
    )

def empty_bbox():
    return {
        "minLat": float("inf"),
        "maxLat": float("-inf"),
        "minLon": float("inf"),
        "maxLon": float("-inf"),
    }

def update_bbox(b, lat, lon):
    b["minLat"] = min(b["minLat"], lat)
    b["maxLat"] = max(b["maxLat"], lat)
    b["minLon"] = min(b["minLon"], lon)
    b["maxLon"] = max(b["maxLon"], lon)

def valid_bbox(b):
    return b["minLat"] != float("inf")

def bbox_row(b):
    if not valid_bbox(b):
        return {
            "minLat": "",
            "maxLat": "",
            "minLon": "",
            "maxLon": "",
            "centerLat": "",
            "centerLon": "",
            "width_m": "",
            "height_m": "",
        }

    width, height = bbox_meters(b["minLon"], b["minLat"], b["maxLon"], b["maxLat"])

    return {
        "minLat": b["minLat"],
        "maxLat": b["maxLat"],
        "minLon": b["minLon"],
        "maxLon": b["maxLon"],
        "centerLat": (b["minLat"] + b["maxLat"]) / 2.0,
        "centerLon": (b["minLon"] + b["maxLon"]) / 2.0,
        "width_m": round(width, 2),
        "height_m": round(height, 2),
    }

def make_geojson_feature(dataset_name, obj):
    coords = obj.get("coords") or []
    pairs = extract_pairs(coords)

    props = dict(obj)
    props.pop("coords", None)
    props["dataset"] = dataset_name

    if dataset_name in LINE_DATASETS:
        if len(pairs) < 2:
            return None

        geometry = {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in pairs],
        }
    else:
        if len(pairs) < 3:
            return None

        ring = [[lon, lat] for lat, lon in pairs]

        if ring[0] != ring[-1]:
            ring.append(ring[0])

        geometry = {
            "type": "Polygon",
            "coordinates": [ring],
        }

    return {
        "type": "Feature",
        "properties": props,
        "geometry": geometry,
    }

datasets = load_datasets(INPUT)

dataset_stats = []
global_bbox = empty_bbox()
property_keys = Counter()
property_values = defaultdict(Counter)

all_features = []
zoning_features = []
transport_features = []

for dataset_name, rows in datasets.items():
    b = empty_bbox()
    feature_count = 0
    coord_count = 0
    geojson_features = []

    if not isinstance(rows, list):
        continue

    for obj in rows:
        if not isinstance(obj, dict):
            continue

        feature_count += 1

        for k, v in obj.items():
            if k == "coords":
                continue
            property_keys[k] += 1
            if k in {"category", "subcategory", "sourceTag", "confidence", "zone", "cs2", "name"}:
                property_values[k][str(v)] += 1

        pairs = extract_pairs(obj.get("coords") or [])
        coord_count += len(pairs)

        for lat, lon in pairs:
            update_bbox(b, lat, lon)
            update_bbox(global_bbox, lat, lon)

        feat = make_geojson_feature(dataset_name, obj)
        if feat:
            geojson_features.append(feat)
            all_features.append(feat)

            if dataset_name in LINE_DATASETS:
                transport_features.append(feat)
            else:
                zoning_features.append(feat)

    row = {
        "dataset": dataset_name,
        "objects": feature_count,
        "coords": coord_count,
        "geometry": "LineString" if dataset_name in LINE_DATASETS else "Polygon",
    }
    row.update(bbox_row(b))
    dataset_stats.append(row)

    out_name = dataset_name.lower().replace("data_", "") + ".geojson"
    out_path = EXPORT_DIR / out_name
    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": geojson_features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )

def write_fc(path, features):
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )

write_fc(EXPORT_DIR / "zoning_polygons.geojson", zoning_features)
write_fc(EXPORT_DIR / "transport_lines.geojson", transport_features)
write_fc(EXPORT_DIR / "all_features.geojson", all_features)

summary_path = OUT_DIR / "summary.txt"
datasets_csv = OUT_DIR / "datasets.csv"
keys_csv = OUT_DIR / "property_keys.csv"
values_csv = OUT_DIR / "property_values.csv"

with summary_path.open("w", encoding="utf-8") as f:
    f.write("ZONING_DATA_JS ANALYSIS\n")
    f.write("=======================\n\n")
    f.write(f"Input: {INPUT}\n")
    f.write(f"Datasets: {len(datasets)}\n")
    f.write(f"Total objects: {sum(r['objects'] for r in dataset_stats)}\n")
    f.write(f"GeoJSON exported features: {len(all_features)}\n\n")

    f.write("GLOBAL BBOX\n")
    g = bbox_row(global_bbox)
    for k, v in g.items():
        f.write(f"{k}: {v}\n")
    f.write("\n")

    f.write("DATASETS\n")
    for r in dataset_stats:
        f.write(
            f"- {r['dataset']}: objects={r['objects']}, coords={r['coords']}, "
            f"size_m={r['width_m']} x {r['height_m']}, "
            f"center={r['centerLat']},{r['centerLon']}\n"
        )

with datasets_csv.open("w", encoding="utf-8-sig", newline="") as f:
    fieldnames = [
        "dataset", "objects", "coords", "geometry",
        "minLat", "maxLat", "minLon", "maxLon",
        "centerLat", "centerLon", "width_m", "height_m",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    for row in dataset_stats:
        writer.writerow(row)

with keys_csv.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["key", "count"])
    for key, count in property_keys.most_common():
        writer.writerow([key, count])

with values_csv.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["key", "value", "count"])
    for key in sorted(property_values):
        for value, count in property_values[key].most_common(200):
            writer.writerow([key, value, count])

print("OK analyse terminée")
print(summary_path)
print(datasets_csv)
print(keys_csv)
print(values_csv)
print()
print("Exports GeoJSON:")
for p in sorted(EXPORT_DIR.glob("*.geojson")):
    print(f"- {p.name}: {p.stat().st_size / 1024 / 1024:.2f} Mo")
