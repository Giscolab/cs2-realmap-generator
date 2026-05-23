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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bbox", default=None, help="south,west,north,east. Default: read reports/extraction_report.json")
    args = parser.parse_args()

    src_pack = Path(args.pack)
    out_pack = Path(args.out)

    bbox_str = args.bbox or read_declared_bbox(src_pack)
    south, west, north, east = parse_bbox(bbox_str)
    clip_box = box(west, south, east, north)

    if out_pack.exists():
        shutil.rmtree(out_pack)

    (out_pack / "geojson").mkdir(parents=True, exist_ok=True)
    (out_pack / "reports").mkdir(parents=True, exist_ok=True)

    if (src_pack / "reports").exists():
        shutil.copytree(src_pack / "reports", out_pack / "reports", dirs_exist_ok=True)

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourcePack": str(src_pack),
        "outputPack": str(out_pack),
        "bbox": bbox_str,
        "bboxOrder": "south,west,north,east",
        "files": [],
    }

    for in_path in sorted((src_pack / "geojson").glob("*.geojson")):
        data = json.loads(in_path.read_text(encoding="utf-8-sig"))
        before = stats(data, south, west, north, east)

        clipped_features = []
        for feature in data.get("features", []):
            clipped_features.extend(clip_feature(feature, clip_box))

        out_data = {
            "type": "FeatureCollection",
            "features": clipped_features,
        }

        after = stats(out_data, south, west, north, east)

        out_path = out_pack / "geojson" / in_path.name
        out_path.write_text(
            json.dumps(out_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        item = {
            "file": f"geojson/{in_path.name}",
            "featuresBefore": len(data.get("features", [])),
            "featuresAfter": len(clipped_features),
            "coordsBefore": before["coords"],
            "outsideBefore": before["outside"],
            "coordsAfter": after["coords"],
            "outsideAfter": after["outside"],
        }
        report["files"].append(item)

        print(
            f"{in_path.name}: outside {before['outside']} -> {after['outside']} "
            f"| features {item['featuresBefore']} -> {item['featuresAfter']}"
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
