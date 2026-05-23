#!/usr/bin/env python3
"""
extract_zoning.py — Pipeline d’extraction OpenStreetMap pour Cities: Skylines II.

Exemples :
    python extract_zoning.py --bbox "48.766147,2.161560,48.945053,2.485657" --city "Paris"
    python extract_zoning.py --bbox "40.70,-74.02,40.83,-73.91" --city "New York"
"""

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from overpass_client import build_paths_query, build_roads_query, query_with_retry
from classifiers import (
    classify_commercial,
    classify_parking,
    classify_path,
    classify_residential,
    classify_road,
)
from cs2_zones import CS2_LABELS, EXAMPLE_BBOX_PARIS, build_queries


ROAD_TAG_KEYS = (
    "highway",
    "lanes",
    "oneway",
    "maxspeed",
    "surface",
    "bridge",
    "tunnel",
    "junction",
    "cycleway",
    "busway",
    "sidewalk",
)


PATH_TAG_KEYS = (
    "highway",
    "surface",
    "bridge",
    "tunnel",
    "lit",
    "access",
    "foot",
    "bicycle",
    "sidewalk",
)



WATER_TAG_KEYS = (
    "waterway",
    "natural",
    "water",
    "landuse",
    "name",
    "intermittent",
    "seasonal",
    "tunnel",
    "bridge",
)


BUNDLE_COUNTRY_CODE_ALIASES = {
    "france": "fr",
    "republique francaise": "fr",
    "république française": "fr",
    "china": "cn",
    "chine": "cn",
    "united states": "us",
    "united states of america": "us",
    "usa": "us",
    "us": "us",
    "etats unis": "us",
    "états unis": "us",
}


def strip_bundle_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def slugify_bundle_part(value: str, fallback: str) -> str:
    ascii_value = strip_bundle_accents(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or fallback


def sanitize_bundle_id(value: str) -> str:
    normalized = strip_bundle_accents(value).lower()
    bundle_id = re.sub(r"[^a-z0-9_.-]+", "_", normalized).strip("_")
    bundle_id = re.sub(r"_+", "_", bundle_id)
    return bundle_id or "bundle"


def bundle_country_slug(country: str, country_code: str | None) -> str:
    if country_code:
        return slugify_bundle_part(country_code, "xx")

    key = slugify_bundle_part(country, "")
    if key in BUNDLE_COUNTRY_CODE_ALIASES:
        return BUNDLE_COUNTRY_CODE_ALIASES[key]

    return slugify_bundle_part(country, "xx")


def build_bundle_id(
    *,
    city: str,
    country: str,
    country_code: str | None,
    center_lon: float,
    center_lat: float,
    explicit_bundle_id: str | None,
) -> str:
    if explicit_bundle_id:
        return sanitize_bundle_id(explicit_bundle_id)

    city_part = slugify_bundle_part(city, "city")
    country_part = bundle_country_slug(country, country_code)

    return f"{city_part}_{country_part}_{center_lat:.6f}_{center_lon:.6f}"


def bbox_center_lon_lat(bbox: str) -> tuple[float, float]:
    try:
        south, west, north, east = [float(part.strip()) for part in bbox.split(",")]
    except ValueError as exc:
        raise SystemExit(f"[ERREUR] BBOX invalide : {bbox}") from exc

    return ((west + east) / 2.0, (south + north) / 2.0)


def build_bundle_geojson_pack_dir(
    *,
    bundle_root: str,
    bundle_id: str,
) -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / bundle_root.strip("\\/") / bundle_id / "geojson_pack"


def build_water_lines_query(bbox: str) -> str:
    return f"""
[out:json][timeout:180];
(
  way["waterway"~"^(river|stream|canal|drain|ditch)$"]({bbox});
);
out tags geom;
"""


def build_water_areas_query(bbox: str) -> str:
    return f"""
[out:json][timeout:180];
(
  way["natural"="water"]({bbox});
  relation["natural"="water"]({bbox});
  way["water"]({bbox});
  relation["water"]({bbox});
  way["landuse"~"^(reservoir|basin)$"]({bbox});
  relation["landuse"~"^(reservoir|basin)$"]({bbox});
  way["waterway"="riverbank"]({bbox});
  relation["waterway"="riverbank"]({bbox});
);
out tags geom;
"""


def extract_water_tags(tags: dict) -> dict:
    return {
        key: tags[key]
        for key in WATER_TAG_KEYS
        if tags.get(key) is not None and str(tags.get(key)).strip() != ""
    }


def classify_water_area(tags: dict) -> str:
    if tags.get("water"):
        return str(tags.get("water"))
    if tags.get("natural") == "water":
        return "water"
    if tags.get("landuse"):
        return str(tags.get("landuse"))
    if tags.get("waterway"):
        return str(tags.get("waterway"))
    return "water"


def classify_water_line(tags: dict) -> str:
    if tags.get("waterway"):
        return str(tags.get("waterway"))
    return "waterway"


def coords_from_way(element: dict) -> list | None:
    geom = element.get("geometry", [])
    if len(geom) < 3:
        return None
    return [[pt["lat"], pt["lon"]] for pt in geom]


def coords_from_line_way(element: dict) -> list | None:
    geom = element.get("geometry", [])
    if len(geom) < 2:
        return None
    return [[pt["lat"], pt["lon"]] for pt in geom]


def coords_from_relation(element: dict) -> list | None:
    members = element.get("members", [])
    outers = [
        m for m in members
        if m.get("role") == "outer" and len(m.get("geometry", [])) > 2
    ]
    if not outers:
        return None
    outers.sort(key=lambda m: len(m["geometry"]), reverse=True)
    return [[pt["lat"], pt["lon"]] for pt in outers[0]["geometry"]]


def extract_coords(element: dict) -> list | None:
    if element.get("type") == "way":
        return coords_from_way(element)
    if element.get("type") == "relation":
        return coords_from_relation(element)
    return None


def extract_line_coords(element: dict) -> list | None:
    if element.get("type") == "way":
        return coords_from_line_way(element)
    return None


def extract_road_tags(tags: dict) -> dict:
    return {
        key: tags[key]
        for key in ROAD_TAG_KEYS
        if tags.get(key) is not None and str(tags.get(key)).strip() != ""
    }


def extract_path_tags(tags: dict) -> dict:
    return {
        key: tags[key]
        for key in PATH_TAG_KEYS
        if tags.get(key) is not None and str(tags.get(key)).strip() != ""
    }


def parse_building_levels(value) -> int:
    if value is None:
        return 0

    text = str(value).strip().replace(",", ".")
    if not text:
        return 0

    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0



MAJOR_ROAD_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}

DRIVEABLE_ROAD_HIGHWAYS = MAJOR_ROAD_HIGHWAYS | {
    "residential",
    "unclassified",
    "living_street",
    "service",
    "road",
}


def slugify_city(value: str) -> str:
    text = str(value or "zone-cs2").strip().lower()
    out = []
    previous_dash = False

    for char in text:
        if char.isalnum():
            out.append(char)
            previous_dash = False
        elif not previous_dash:
            out.append("-")
            previous_dash = True

    slug = "".join(out).strip("-")
    return slug or "zone-cs2"


def default_pack_dir(city: str) -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "exports" / slugify_city(city)


def latlon_to_lonlat(coords: list) -> list:
    return [[point[1], point[0]] for point in coords]


def close_polygon_ring(coords: list) -> list:
    ring = latlon_to_lonlat(coords)

    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])

    return ring


def feature_properties(item: dict) -> dict:
    return {
        key: value
        for key, value in item.items()
        if key != "coords"
    }


def polygon_feature(item: dict) -> dict | None:
    coords = item.get("coords") or []
    ring = close_polygon_ring(coords)

    if len(ring) < 4:
        return None

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
        "properties": feature_properties(item),
    }


def line_feature(item: dict) -> dict | None:
    coords = item.get("coords") or []
    line = latlon_to_lonlat(coords)

    if len(line) < 2:
        return None

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": line,
        },
        "properties": feature_properties(item),
    }


def feature_collection(features: list) -> dict:
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def build_features(items: list, geometry_type: str) -> list:
    features = []

    for item in items:
        if geometry_type == "polygon":
            feature = polygon_feature(item)
        elif geometry_type == "line":
            feature = line_feature(item)
        else:
            raise ValueError(f"Type de géométrie non supporté : {geometry_type}")

        if feature is not None:
            features.append(feature)

    return features


def write_geojson(path: Path, features: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(feature_collection(features), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def road_highway_value(item: dict) -> str:
    tags = item.get("tags") or {}
    value = tags.get("highway") or item.get("sourceTag") or ""
    return str(value).strip().lower()


def is_major_road(item: dict) -> bool:
    return road_highway_value(item) in MAJOR_ROAD_HIGHWAYS


def is_driveable_road(item: dict) -> bool:
    return road_highway_value(item) in DRIVEABLE_ROAD_HIGHWAYS


def write_split_layers_pack(
    output: dict[str, list],
    city: str,
    bbox: str,
    out_dir: Path,
    generated_at: str,
    report: dict,
) -> None:
    zone_categories = [
        "residential",
        "commercial",
        "industrial",
        "retail",
        "parking",
        "office",
        "mixed",
    ]

    geojson_dir = out_dir / "geojson"
    reports_dir = out_dir / "reports"

    base_features = []
    layer_index = {
        "generatedAt": generated_at,
        "city": city,
        "bbox": bbox,
        "bboxOrder": "south,west,north,east",
        "layers": [],
    }

    def write_layer(name: str, features: list, geometry_type: str, base_layer: bool = True) -> None:
        relative_path = f"geojson/{name}"
        write_geojson(out_dir / relative_path, features)

        if base_layer:
            base_features.extend(features)

        layer_index["layers"].append({
            "name": name.replace(".geojson", ""),
            "file": relative_path,
            "geometryType": geometry_type,
            "count": len(features),
        })

    zoning_features = []

    for cat in zone_categories:
        features = build_features(output.get(cat, []), "polygon")
        zoning_features.extend(features)
        write_layer(f"{cat}.geojson", features, "Polygon", base_layer=True)

    write_layer(
        "zoning_polygons.geojson",
        zoning_features,
        "Polygon",
        base_layer=False,
    )

    road_items = output.get("roads", [])
    road_features = build_features(road_items, "line")
    write_layer("roads.geojson", road_features, "LineString", base_layer=True)

    major_road_features = build_features(
        [item for item in road_items if is_major_road(item)],
        "line",
    )
    write_layer(
        "roads_major_clipped.geojson",
        major_road_features,
        "LineString",
        base_layer=False,
    )

    driveable_road_features = build_features(
        [item for item in road_items if is_driveable_road(item)],
        "line",
    )
    write_layer(
        "roads_driveable_clipped.geojson",
        driveable_road_features,
        "LineString",
        base_layer=False,
    )

    path_features = build_features(output.get("paths", []), "line")
    write_layer("paths.geojson", path_features, "LineString", base_layer=True)

    water_line_features = build_features(output.get("water_lines", []), "line")
    write_layer(
        "water_lines_clipped.geojson",
        water_line_features,
        "LineString",
        base_layer=True,
    )

    water_area_features = build_features(output.get("water_areas", []), "polygon")
    write_layer(
        "water_areas_clipped.geojson",
        water_area_features,
        "Polygon",
        base_layer=True,
    )

    write_geojson(geojson_dir / "all_features.geojson", base_features)

    layer_index["layers"].append({
        "name": "all_features",
        "file": "geojson/all_features.geojson",
        "geometryType": "Mixed",
        "count": len(base_features),
    })

    reports_dir.mkdir(parents=True, exist_ok=True)

    (reports_dir / "layer_index.json").write_text(
        json.dumps(layer_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    extraction_report = {
        "generatedAt": generated_at,
        "city": city,
        "bbox": bbox,
        "bboxOrder": "south,west,north,east",
        "outputDirectory": str(out_dir),
        "summary": report,
        "layers": layer_index["layers"],
        "notes": [
            "Les coordonnées GeoJSON sont exportées en ordre standard [longitude, latitude].",
            "Les fichiers water_lines_clipped.geojson et water_areas_clipped.geojson sont produits depuis les tags OSM waterway/natural/water/landuse.",
        ],
    }

    (reports_dir / "extraction_report.json").write_text(
        json.dumps(extraction_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Extrait les données de zonage OpenStreetMap pour Cities: Skylines II"
    )
    parser.add_argument(
        "--bbox",
        default=EXAMPLE_BBOX_PARIS,
        help="Boîte géographique au format 'sud,ouest,nord,est'. Par défaut : exemple Paris.",
    )
    parser.add_argument(
        "--city",
        default="Ville personnalisée",
        help="Nom de la ville ou zone extraite.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Dossier de sortie du pack GeoJSON scindé. Exemple : ../exports/zone-cs2",
    )
    parser.add_argument(
        "--bundle-output",
        action="store_true",
        help="Exporte le pack GeoJSON dans exports/bundles/<bundle_id>/geojson_pack.",
    )
    parser.add_argument(
        "--bundle-root",
        default="exports/bundles",
        help="Dossier racine des bundles si --bundle-output est actif.",
    )
    parser.add_argument(
        "--bundle-id",
        default=None,
        help="Identifiant du bundle. Si absent, il est généré depuis ville/pays/centre bbox.",
    )
    parser.add_argument(
        "--country",
        default="",
        help="Pays utilisé pour générer le bundle_id si --bundle-output est actif.",
    )
    parser.add_argument(
        "--country-code",
        default=None,
        help="Code pays court utilisé pour générer le bundle_id si --bundle-output est actif.",
    )
    parser.add_argument(
        "--split-layers",
        action="store_true",
        help="Conservé pour compatibilité CLI ; le pack GeoJSON est toujours scindé par type.",
    )

    args = parser.parse_args()

    bbox = args.bbox
    city = args.city
    if args.bundle_output:
        center_lon, center_lat = bbox_center_lon_lat(bbox)
        bundle_id = build_bundle_id(
            city=city,
            country=args.country,
            country_code=args.country_code,
            center_lon=center_lon,
            center_lat=center_lat,
            explicit_bundle_id=args.bundle_id,
        )
        pack_dir = build_bundle_geojson_pack_dir(
            bundle_root=args.bundle_root,
            bundle_id=bundle_id,
        )
    else:
        bundle_id = None
        pack_dir = Path(args.out_dir) if args.out_dir else default_pack_dir(city)

    queries = build_queries(bbox)

    print("CS2 Realmap Generator - extraction OpenStreetMap")
    print(f"Ville / zone : {city}")
    print(f"BBOX         : {bbox}")
    if args.bundle_output:
        print(f"Bundle ID    : {bundle_id}")
        print(f"Bundle root  : {args.bundle_root}")
    print(f"Pack exports : {pack_dir}")
    print()

    print("[1/4] Construction de l’index de densité résidentielle...")
    bld_data = query_with_retry(queries["buildings_levels"], "buildings_levels")
    building_index: dict[int, int] = {}

    for el in bld_data.get("elements", []):
        tags = el.get("tags") or {}
        lvl = parse_building_levels(tags.get("building:levels"))

        if lvl > 0 and "id" in el:
            building_index[el["id"]] = lvl

    print(f"      Index : {len(building_index)} bâtiments avec données d’étages\n")

    print("[2/4] Téléchargement des polygones de zonage...")
    zone_categories = ["residential", "commercial", "industrial", "retail", "parking", "office", "mixed"]
    raw: dict[str, list] = {}

    for cat in zone_categories:
        result = query_with_retry(queries[cat], cat)
        raw[cat] = result.get("elements", [])
        print(f"      {cat}: {len(raw[cat])} éléments")

    print("\n[3/4] Téléchargement des routes et chemins...")
    roads_data = query_with_retry(build_roads_query(bbox), "roads")
    raw["roads"] = roads_data.get("elements", [])
    print(f"      roads: {len(raw['roads'])} éléments")
    paths_data = query_with_retry(build_paths_query(bbox), "paths")
    raw["paths"] = paths_data.get("elements", [])
    print(f"      paths: {len(raw['paths'])} éléments")

    water_lines_data = query_with_retry(build_water_lines_query(bbox), "water_lines")
    raw["water_lines"] = water_lines_data.get("elements", [])
    print(f"      water_lines: {len(raw['water_lines'])} éléments")

    water_areas_data = query_with_retry(build_water_areas_query(bbox), "water_areas")
    raw["water_areas"] = water_areas_data.get("elements", [])
    print(f"      water_areas: {len(raw['water_areas'])} éléments")

    print("\n[4/4] Classification des zones, routes et chemins...")

    output: dict[str, list] = {cat: [] for cat in zone_categories}
    output["roads"] = []
    output["paths"] = []
    output["water_lines"] = []
    output["water_areas"] = []
    skipped = 0
    skipped_roads = 0
    skipped_paths = 0
    skipped_water_lines = 0
    skipped_water_areas = 0
    commercial_ids: set[int] = set()

    for el in raw["commercial"]:
        if "id" in el:
            commercial_ids.add(el["id"])

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        zone = classify_commercial(tags)

        output["commercial"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": zone,
            "cs2": CS2_LABELS[f"com_{zone}"],
        })

    for el in raw["residential"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        zone = classify_residential(tags, building_index, el.get("id"))
        cs2_key = {"high": "res_high", "medium": "res_med", "low": "res_low"}[zone]

        output["residential"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": zone,
            "cs2": CS2_LABELS[cs2_key],
        })

    for el in raw["industrial"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["industrial"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": "industrial",
            "cs2": CS2_LABELS["industrial"],
        })

    for el in raw["retail"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["retail"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": "retail",
            "cs2": CS2_LABELS["retail"],
        })

    for el in raw["parking"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        zone = classify_parking(tags)

        output["parking"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": zone,
            "cs2": CS2_LABELS[f"prk_{zone}"],
        })

    for el in raw["office"]:
        if el.get("id") in commercial_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["office"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": "office",
            "cs2": CS2_LABELS["office"],
        })

    for el in raw["mixed"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["mixed"].append({
            "id": el.get("id"),
            "name": tags.get("name", ""),
            "coords": coords,
            "zone": "mixed",
            "cs2": CS2_LABELS["mixed"],
        })

    for el in raw["roads"]:
        tags = el.get("tags") or {}
        coords = extract_line_coords(el)

        if not coords:
            skipped_roads += 1
            continue

        classification = classify_road(tags)

        output["roads"].append({
            "id": el.get("id"),
            "name": tags.get("name") or "Néant",
            "category": "Roads",
            "subcategory": classification["subcategory"],
            "sourceTag": classification["sourceTag"],
            "confidence": classification["confidence"],
            "coords": coords,
            "tags": extract_road_tags(tags),
        })

    for el in raw["paths"]:
        tags = el.get("tags") or {}
        coords = extract_line_coords(el)

        if not coords:
            skipped_paths += 1
            continue

        classification = classify_path(tags)

        output["paths"].append({
            "id": el.get("id"),
            "name": tags.get("name") or "Néant",
            "category": "Paths",
            "subcategory": classification["subcategory"],
            "sourceTag": classification["sourceTag"],
            "confidence": classification["confidence"],
            "coords": coords,
            "tags": extract_path_tags(tags),
        })

    for el in raw["water_lines"]:
        tags = el.get("tags") or {}
        coords = extract_line_coords(el)

        if not coords:
            skipped_water_lines += 1
            continue

        subtype = classify_water_line(tags)

        output["water_lines"].append({
            "id": el.get("id"),
            "name": tags.get("name") or "Néant",
            "category": "Water",
            "subcategory": subtype,
            "sourceTag": tags.get("waterway") or "",
            "confidence": 1.0,
            "coords": coords,
            "tags": extract_water_tags(tags),
        })

    for el in raw["water_areas"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped_water_areas += 1
            continue

        subtype = classify_water_area(tags)

        output["water_areas"].append({
            "id": el.get("id"),
            "name": tags.get("name") or "Néant",
            "category": "Water",
            "subcategory": subtype,
            "sourceTag": tags.get("water") or tags.get("natural") or tags.get("landuse") or tags.get("waterway") or "",
            "confidence": 1.0,
            "coords": coords,
            "tags": extract_water_tags(tags),
        })

    total = sum(len(v) for v in output.values())
    res = output["residential"]
    com = output["commercial"]
    roads = output["roads"]
    paths = output["paths"]

    print(f"\n  Résidentiel haut/moyen/bas : "
          f"{sum(1 for r in res if r['zone'] == 'high')} / "
          f"{sum(1 for r in res if r['zone'] == 'medium')} / "
          f"{sum(1 for r in res if r['zone'] == 'low')}")

    print(f"  Commercial haut/bas        : "
          f"{sum(1 for c in com if c['zone'] == 'high')} / "
          f"{sum(1 for c in com if c['zone'] == 'low')}")

    for cat in ["industrial", "retail", "parking", "office", "mixed"]:
        print(f"  {cat:<12}              : {len(output[cat])}")

    print(f"  Routes récupérées          : {len(roads)}")
    print(f"  Chemins/piéton récupérés   : {len(paths)}")
    print(f"  Lignes d’eau récupérées    : {len(output['water_lines'])}")
    print(f"  Zones d’eau récupérées     : {len(output['water_areas'])}")
    print(f"  Ignorés sans géométrie     : {skipped}")
    print(f"  Routes ignorées sans géom. : {skipped_roads}")
    print(f"  Chemins ignorés sans géom. : {skipped_paths}")
    print(f"  Lignes eau sans géom.      : {skipped_water_lines}")
    print(f"  Zones eau sans géom.       : {skipped_water_areas}")
    print(f"  TOTAL                      : {total}")

    ts = datetime.now(timezone.utc).isoformat()

    split_report = {
        "total": total,
        "skippedPolygonsWithoutGeometry": skipped,
        "skippedRoadsWithoutGeometry": skipped_roads,
        "skippedPathsWithoutGeometry": skipped_paths,
        "counts": {
            cat: len(output.get(cat, []))
            for cat in zone_categories + ["roads", "paths", "water_lines", "water_areas"]
        },
    }

    write_split_layers_pack(
        output=output,
        city=city,
        bbox=bbox,
        out_dir=pack_dir,
        generated_at=ts,
        report=split_report,
    )

    print(f"\nPack GeoJSON scindé : {pack_dir}")


if __name__ == "__main__":
    main()
