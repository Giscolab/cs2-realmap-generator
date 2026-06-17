import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "visualizer" / "zoning_data.js"
OUT_DIR = ROOT / "analysis_zoning_data"
EXPORT_DIR = OUT_DIR / "exports"

OUT_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

INTERESTING_KEYS = {
    "highway",
    "waterway",
    "natural",
    "landuse",
    "amenity",
    "leisure",
    "building",
    "shop",
    "office",
    "zoning",
    "zone",
    "category",
    "class",
    "type",
    "name",
    "surface",
    "usage",
    "use",
    "density",
    "cs2",
    "cs2_zone",
    "cs2Zone",
    "zoneType",
    "garmentCategory"
}

def find_matching_json(text, start):
    opener = text[start]
    closer = "}" if opener == "{" else "]"
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

    raise ValueError("JSON non terminé")

def load_js_json(path):
    text = path.read_text(encoding="utf-8-sig")

    starts = [i for i, ch in enumerate(text) if ch in "{["]
    last_error = None

    for start in starts[:200]:
        try:
            payload = find_matching_json(text, start)
            return json.loads(payload)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Impossible d'extraire un JSON depuis {path}. Dernière erreur: {last_error}")

def iter_features(obj, path="root"):
    if isinstance(obj, dict):
        obj_type = obj.get("type")

        if obj_type == "FeatureCollection":
            for i, feature in enumerate(obj.get("features", [])):
                if isinstance(feature, dict):
                    yield feature, f"{path}.features[{i}]"
            return

        if obj_type == "Feature":
            yield obj, path
            return

        for key, value in obj.items():
            yield from iter_features(value, f"{path}.{key}")

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from iter_features(value, f"{path}[{i}]")

def iter_coords_from_any(obj):
    if obj is None:
        return

    if isinstance(obj, list):
        if (
            len(obj) >= 2
            and isinstance(obj[0], (int, float))
            and isinstance(obj[1], (int, float))
        ):
            yield float(obj[0]), float(obj[1])
        else:
            for item in obj:
                yield from iter_coords_from_any(item)

def iter_coords_from_geom(geom):
    if not isinstance(geom, dict):
        return

    geom_type = geom.get("type")

    if geom_type == "GeometryCollection":
        for sub in geom.get("geometries", []):
            yield from iter_coords_from_geom(sub)
    else:
        yield from iter_coords_from_any(geom.get("coordinates"))

def bbox_meters(min_lon, min_lat, max_lon, max_lat):
    center_lat = (min_lat + max_lat) / 2.0
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(center_lat))

    width = (max_lon - min_lon) * meters_per_deg_lon
    height = (max_lat - min_lat) * meters_per_deg_lat
    return width, height

def norm_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)

def lower_props(props):
    out = {}
    for key, value in props.items():
        out[str(key).lower()] = value
    return out

def classify_feature(feature):
    props = feature.get("properties") or {}
    p = lower_props(props)

    text_blob = " ".join(
        norm_value(v).lower()
        for v in props.values()
        if v is not None
    )

    if "waterway" in p:
        return "water"

    if p.get("natural") == "water":
        return "water"

    if norm_value(p.get("landuse")).lower() in {"reservoir", "basin"}:
        return "water"

    if "water" in text_blob or "river" in text_blob or "creek" in text_blob:
        return "water"

    if "highway" in p:
        return "roads"

    if "road" in text_blob or "street" in text_blob or "route" in text_blob:
        return "roads"

    if "building" in p:
        return "buildings"

    if any(k in p for k in ("zoning", "zone", "landuse", "cs2_zone", "cs2zone", "zonetype")):
        return "zoning"

    if any(k in p for k in ("amenity", "leisure", "shop", "office")):
        return "poi"

    return "other"

def update_bbox(acc, lon, lat):
    acc["min_lon"] = min(acc["min_lon"], lon)
    acc["max_lon"] = max(acc["max_lon"], lon)
    acc["min_lat"] = min(acc["min_lat"], lat)
    acc["max_lat"] = max(acc["max_lat"], lat)

def empty_bbox():
    return {
        "min_lon": float("inf"),
        "max_lon": float("-inf"),
        "min_lat": float("inf"),
        "max_lat": float("-inf"),
    }

def bbox_valid(b):
    return (
        b["min_lon"] != float("inf")
        and b["max_lon"] != float("-inf")
        and b["min_lat"] != float("inf")
        and b["max_lat"] != float("-inf")
    )

def bbox_text(b):
    if not bbox_valid(b):
        return "-"
    width, height = bbox_meters(b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"])
    center_lon = (b["min_lon"] + b["max_lon"]) / 2.0
    center_lat = (b["min_lat"] + b["max_lat"]) / 2.0
    return (
        f"minLon={b['min_lon']}, maxLon={b['max_lon']}, "
        f"minLat={b['min_lat']}, maxLat={b['max_lat']}, "
        f"centerLon={center_lon}, centerLat={center_lat}, "
        f"size_m={width:.2f} x {height:.2f}"
    )

print(f"Lecture: {INPUT}")
data = load_js_json(INPUT)

features = list(iter_features(data))
print(f"Features trouvées: {len(features)}")

global_bbox = empty_bbox()
geometry_counts = Counter()
property_key_counts = Counter()
interesting_values = defaultdict(Counter)
classified_counts = Counter()
classified_geom_counts = defaultdict(Counter)
classified_bbox = defaultdict(empty_bbox)
classified_features = defaultdict(list)

for feature, path in features:
    geom = feature.get("geometry")
    props = feature.get("properties") or {}

    geom_type = geom.get("type") if isinstance(geom, dict) else "None"
    geometry_counts[geom_type] += 1

    group = classify_feature(feature)
    classified_counts[group] += 1
    classified_geom_counts[group][geom_type] += 1
    classified_features[group].append(feature)

    for key, value in props.items():
        key_s = str(key)
        property_key_counts[key_s] += 1

        if key_s in INTERESTING_KEYS or key_s.lower() in {k.lower() for k in INTERESTING_KEYS}:
            interesting_values[key_s][norm_value(value)] += 1

    for lon, lat in iter_coords_from_geom(geom):
        update_bbox(global_bbox, lon, lat)
        update_bbox(classified_bbox[group], lon, lat)

summary_path = OUT_DIR / "summary.txt"
keys_path = OUT_DIR / "property_keys.csv"
values_path = OUT_DIR / "interesting_values.csv"
groups_path = OUT_DIR / "groups.csv"

with summary_path.open("w", encoding="utf-8") as f:
    f.write("ZONING_DATA SUMMARY\n")
    f.write("===================\n\n")
    f.write(f"Input: {INPUT}\n")
    f.write(f"Features: {len(features)}\n\n")

    f.write("GLOBAL BOUNDS\n")
    f.write(bbox_text(global_bbox) + "\n\n")

    f.write("GEOMETRY COUNTS\n")
    for key, count in geometry_counts.most_common():
        f.write(f"- {key}: {count}\n")
    f.write("\n")

    f.write("CLASSIFIED GROUPS\n")
    for group, count in classified_counts.most_common():
        f.write(f"- {group}: {count}\n")
        f.write(f"  {bbox_text(classified_bbox[group])}\n")
        for geom_type, geom_count in classified_geom_counts[group].most_common():
            f.write(f"  geom {geom_type}: {geom_count}\n")
    f.write("\n")

    f.write("TOP PROPERTY KEYS\n")
    for key, count in property_key_counts.most_common(80):
        f.write(f"- {key}: {count}\n")

with keys_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["property_key", "count"])
    for key, count in property_key_counts.most_common():
        writer.writerow([key, count])

with values_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["property_key", "value", "count"])
    for key in sorted(interesting_values):
        for value, count in interesting_values[key].most_common(200):
            writer.writerow([key, value, count])

with groups_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow([
        "group",
        "count",
        "minLon",
        "maxLon",
        "minLat",
        "maxLat",
        "centerLon",
        "centerLat",
        "width_m",
        "height_m",
        "geometry_counts",
    ])

    for group, count in classified_counts.most_common():
        b = classified_bbox[group]
        if bbox_valid(b):
            width, height = bbox_meters(b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"])
            center_lon = (b["min_lon"] + b["max_lon"]) / 2.0
            center_lat = (b["min_lat"] + b["max_lat"]) / 2.0
        else:
            width = height = center_lon = center_lat = ""

        writer.writerow([
            group,
            count,
            b["min_lon"] if bbox_valid(b) else "",
            b["max_lon"] if bbox_valid(b) else "",
            b["min_lat"] if bbox_valid(b) else "",
            b["max_lat"] if bbox_valid(b) else "",
            center_lon,
            center_lat,
            width,
            height,
            dict(classified_geom_counts[group]),
        ])

for group, feats in classified_features.items():
    if not feats:
        continue

    out_geojson = {
        "type": "FeatureCollection",
        "features": feats,
    }

    out_path = EXPORT_DIR / f"{group}.geojson"
    out_path.write_text(
        json.dumps(out_geojson, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )

print()
print("OK. Rapports générés:")
print(f"- {summary_path}")
print(f"- {keys_path}")
print(f"- {values_path}")
print(f"- {groups_path}")
print()
print("GeoJSON extraits:")
for path in sorted(EXPORT_DIR.glob("*.geojson")):
    print(f"- {path} ({path.stat().st_size / 1024 / 1024:.2f} Mo)")
