import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "analysis_zoning_data" / "clipped" / "roads.geojson"
OUT_DIR = ROOT / "analysis_zoning_data" / "clipped"

MAJOR_TAGS = {
    "highway=motorway",
    "highway=motorway_link",
    "highway=trunk",
    "highway=trunk_link",
    "highway=primary",
    "highway=primary_link",
    "highway=secondary",
    "highway=secondary_link",
    "highway=tertiary",
    "highway=tertiary_link",
}

DRIVEABLE_TAGS = MAJOR_TAGS | {
    "highway=residential",
    "highway=unclassified",
    "highway=living_street",
}

def load_geojson(path):
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

def filter_by_tags(features, allowed_tags):
    out = []
    counts = Counter()

    for feature in features:
        props = feature.get("properties") or {}
        source_tag = props.get("sourceTag", "")

        counts[source_tag] += 1

        if source_tag in allowed_tags:
            out.append(feature)

    return out, counts

data = load_geojson(INPUT)
features = data.get("features", [])

major_features, counts = filter_by_tags(features, MAJOR_TAGS)
driveable_features, _ = filter_by_tags(features, DRIVEABLE_TAGS)

major_path = OUT_DIR / "roads_major_clipped.geojson"
driveable_path = OUT_DIR / "roads_driveable_clipped.geojson"

write_geojson(major_path, major_features)
write_geojson(driveable_path, driveable_features)

print("INPUT:", INPUT)
print("Total roads:", len(features))
print()

print("MAJOR roads:", len(major_features))
print("Output:", major_path)
print(f"Size: {major_path.stat().st_size / 1024 / 1024:.2f} Mo")
print()

print("DRIVEABLE roads:", len(driveable_features))
print("Output:", driveable_path)
print(f"Size: {driveable_path.stat().st_size / 1024 / 1024:.2f} Mo")
print()

print("SourceTag counts:")
for tag, count in counts.most_common():
    marker = "KEEP_MAJOR" if tag in MAJOR_TAGS else ("KEEP_DRIVEABLE" if tag in DRIVEABLE_TAGS else "DROP")
    print(f"{marker:14} {tag:24} {count}")
