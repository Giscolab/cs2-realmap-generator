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

from country_codes import UnknownCountryCodeError, resolve_country_code
from overpass_client import build_paths_query, build_roads_query, query_with_retry
from classifiers import (
    classify_commercial,
    classify_parking,
    classify_path,
    classify_residential,
    classify_road,
)
from cs2_zones import CS2_LABELS, EXAMPLE_BBOX_PARIS, build_queries
from road_categories import (
    ROAD_CATEGORIES,
    classify_road_category,
    road_category_color,
    road_category_label,
)
from railways import build_railways_query, is_active_railway, railway_item
from service_families import (
    SERVICE_FAMILIES,
    build_service_query,
    classify_service_element,
    service_point,
    service_tags,
    source_tag,
    subcategory_labels,
)


ROAD_TAG_KEYS = (
    "name",
    "ref",
    "highway",
    "lanes",
    "lanes:forward",
    "lanes:backward",
    "oneway",
    "maxspeed",
    "width",
    "surface",
    "smoothness",
    "tracktype",
    "bridge",
    "tunnel",
    "layer",
    "junction",
    "service",
    "access",
    "motor_vehicle",
    "cycleway",
    "busway",
    "sidewalk",
    "lit",
    "toll",
)


PATH_TAG_KEYS = (
    "name",
    "ref",
    "highway",
    "surface",
    "smoothness",
    "width",
    "bridge",
    "tunnel",
    "layer",
    "lit",
    "access",
    "foot",
    "bicycle",
    "sidewalk",
)


ZONE_TAG_KEYS = (
    "name",
    "official_name",
    "operator",
    "ref",
    "landuse",
    "building",
    "building:part",
    "building:use",
    "building:levels",
    "building:levels:underground",
    "levels",
    "residential",
    "mixed_use",
    "shop",
    "office",
    "industrial",
    "amenity",
    "parking",
    "parking:levels",
    "access",
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
    "layer",
    "tidal",
    "width",
)


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
    try:
        return resolve_country_code(country_code, country)
    except UnknownCountryCodeError as exc:
        raise SystemExit(f"[ERREUR] {exc}") from exc


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


def _coord_key(point: list) -> tuple[float, float]:
    return (round(float(point[0]), 9), round(float(point[1]), 9))


def _member_segment(member: dict) -> list:
    return [
        [point["lat"], point["lon"]]
        for point in member.get("geometry") or []
        if point.get("lat") is not None and point.get("lon") is not None
    ]


def _merge_member_segments(members: list[dict]) -> list[list]:
    """Réassemble les ways d'une relation multipolygon en anneaux fermés.

    Overpass renvoie souvent un contour de relation sous forme de plusieurs
    membres de deux points. L'ancien extracteur ignorait tous ces membres puis
    ne gardait que le plus long contour déjà fermé, ce qui supprimait des îles
    entières et la plupart des grandes relations administrées par segments.
    """
    remaining = [segment for member in members if len(segment := _member_segment(member)) >= 2]
    rings: list[list] = []

    while remaining:
        chain = remaining.pop(0)
        merged = True

        while merged and remaining and _coord_key(chain[0]) != _coord_key(chain[-1]):
            merged = False
            for index, segment in enumerate(remaining):
                chain_start = _coord_key(chain[0])
                chain_end = _coord_key(chain[-1])
                segment_start = _coord_key(segment[0])
                segment_end = _coord_key(segment[-1])

                if chain_end == segment_start:
                    chain.extend(segment[1:])
                elif chain_end == segment_end:
                    chain.extend(reversed(segment[:-1]))
                elif chain_start == segment_end:
                    chain = segment[:-1] + chain
                elif chain_start == segment_start:
                    chain = list(reversed(segment[1:])) + chain
                else:
                    continue

                remaining.pop(index)
                merged = True
                break

        if len(chain) >= 3:
            if _coord_key(chain[0]) != _coord_key(chain[-1]):
                chain.append(chain[0])
            rings.append(chain)

    return rings


def _ring_area(ring: list) -> float:
    area = 0.0
    for left, right in zip(ring, ring[1:]):
        area += float(left[1]) * float(right[0]) - float(right[1]) * float(left[0])
    return abs(area) / 2.0


def _point_in_ring(point: list, ring: list) -> bool:
    y, x = float(point[0]), float(point[1])
    inside = False
    previous = ring[-1]

    for current in ring:
        y1, x1 = float(previous[0]), float(previous[1])
        y2, x2 = float(current[0]), float(current[1])
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            denominator = y2 - y1
            intersection_x = x1 + (x2 - x1) * (y - y1) / denominator
            if x < intersection_x:
                inside = not inside
        previous = current

    return inside


def polygon_parts_from_relation(element: dict) -> list[dict]:
    members = element.get("members") or []
    outer_members = [member for member in members if member.get("role") == "outer"]
    if not outer_members:
        # Certaines anciennes relations multipolygon omettent le rôle outer.
        outer_members = [member for member in members if member.get("role") != "inner"]

    outer_rings = _merge_member_segments(outer_members)
    inner_rings = _merge_member_segments(
        [member for member in members if member.get("role") == "inner"]
    )
    parts = [{"outer": ring, "inners": []} for ring in outer_rings]

    for inner in inner_rings:
        containers = [
            part for part in parts
            if inner and _point_in_ring(inner[0], part["outer"])
        ]
        if containers:
            min(containers, key=lambda part: _ring_area(part["outer"]))["inners"].append(inner)

    return sorted(parts, key=lambda part: _ring_area(part["outer"]), reverse=True)


def extract_polygon_parts(element: dict) -> list[dict]:
    if element.get("type") == "way":
        coords = coords_from_way(element)
        return [{"outer": coords, "inners": []}] if coords else []
    if element.get("type") == "relation":
        return polygon_parts_from_relation(element)
    return []


def coords_from_relation(element: dict) -> list | None:
    parts = polygon_parts_from_relation(element)
    return parts[0]["outer"] if parts else None


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


def extract_zone_tags(tags: dict) -> dict:
    return {
        key: tags[key]
        for key in ZONE_TAG_KEYS
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


def osm_element_key(element: dict) -> tuple[str, int] | None:
    """Clé stable sans collision entre espaces node/way/relation OSM."""
    element_id = element.get("id")
    if element_id is None:
        return None
    return (str(element.get("type") or ""), int(element_id))



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
        if key not in {"coords", "polygonParts"}
    }


def polygon_feature(item: dict) -> dict | None:
    parts = item.get("polygonParts") or [
        {"outer": item.get("coords") or [], "inners": []}
    ]
    polygons = []

    for part in parts:
        outer = close_polygon_ring(part.get("outer") or [])
        if len(outer) < 4:
            continue
        inner_rings = [
            ring
            for coords in part.get("inners") or []
            if len(ring := close_polygon_ring(coords)) >= 4
        ]
        polygons.append([outer, *inner_rings])

    if not polygons:
        return None

    if len(polygons) == 1:
        geometry = {"type": "Polygon", "coordinates": polygons[0]}
    else:
        geometry = {"type": "MultiPolygon", "coordinates": polygons}

    return {
        "type": "Feature",
        "geometry": geometry,
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


def feature_collection(features: list, metadata: dict | None = None) -> dict:
    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    if metadata:
        collection.update(metadata)
    return collection


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


def write_geojson(path: Path, features: list, metadata: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(feature_collection(features, metadata), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def road_highway_value(item: dict) -> str:
    tags = item.get("tags") or {}
    value = tags.get("highway") or item.get("sourceTag") or ""
    return str(value).strip().lower()


def is_major_road(item: dict) -> bool:
    return road_highway_value(item) in MAJOR_ROAD_HIGHWAYS


def is_driveable_road(item: dict) -> bool:
    # build_roads_query a déjà écarté chemins et cycles de vie inactifs.
    # Ce sous-ensemble historique est la source chargée par défaut dans le mod :
    # il doit donc conserver aussi track, road et toute valeur highway active
    # future classée en fallback, sinon elle serait comptée mais invisible.
    return bool(road_highway_value(item))


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
        "contracts": {
            "all_features": {
                "scope": "legacy-base-overlays",
                "includes": [
                    *zone_categories,
                    "roads",
                    "paths",
                    "water_lines",
                    "water_areas",
                ],
                "excludesIndependentSources": [
                    "railways",
                    "services/*",
                ],
                "reason": "railways and services keep one authoritative geometry source",
            },
        },
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

    road_category_layers = []
    for road_category in ROAD_CATEGORIES:
        if road_category["key"] == "pathway":
            continue
        category_items = [
            item for item in road_items
            if item.get("roadCategory") == road_category["key"]
        ]
        category_features = build_features(category_items, "line")
        category_file = f"roads_{road_category['key']}.geojson"
        write_layer(category_file, category_features, "LineString", base_layer=False)
        road_category_layers.append({
            "key": road_category["key"],
            "label": road_category["label"],
            "color": road_category["color"],
            "file": f"geojson/{category_file}",
            "count": len(category_features),
        })

    railway_features = build_features(output.get("railways", []), "line")
    # Source ferroviaire unique : elle est indexée, mais volontairement absente
    # de all_features.geojson et n'est jamais scindée par type ou service.
    write_layer(
        "railways.geojson",
        railway_features,
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

    all_features_contract = layer_index["contracts"]["all_features"]
    write_geojson(
        geojson_dir / "all_features.geojson",
        base_features,
        metadata={
            "scope": all_features_contract["scope"],
            "includes": all_features_contract["includes"],
            "excludesIndependentSources": all_features_contract["excludesIndependentSources"],
        },
    )

    layer_index["layers"].append({
        "name": "all_features",
        "file": "geojson/all_features.geojson",
        "geometryType": "Mixed",
        "count": len(base_features),
        "scope": all_features_contract["scope"],
        "excludesIndependentSources": all_features_contract["excludesIndependentSources"],
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
            "railways.geojson est un calque visuel indépendant et sa géométrie n'est pas dupliquée dans all_features.geojson.",
            "Les services restent dans geojson/services/*.geojson et ne sont pas dupliqués dans all_features.geojson.",
            "all_features.geojson est l'agrégat historique des overlays de base, pas le total de toutes les sources du bundle.",
        ],
    }

    (reports_dir / "extraction_report.json").write_text(
        json.dumps(extraction_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    road_category_layers.append({
        "key": "pathway",
        "label": road_category_label("pathway"),
        "color": road_category_color("pathway"),
        "file": "geojson/paths.geojson",
        "count": len(path_features),
    })

    roads_index = {
        "generatedAt": generated_at,
        "bbox": bbox,
        "bboxOrder": "south,west,north,east",
        "categories": road_category_layers,
    }
    (reports_dir / "roads_index.json").write_text(
        json.dumps(roads_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def service_point_feature(item: dict) -> dict:
    lat, lon = item["point"]
    properties = {key: value for key, value in item.items() if key != "point"}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def download_service_families(bbox: str, query_fn=query_with_retry) -> dict:
    services: dict[str, list] = {}

    for family in SERVICE_FAMILIES:
        items: list = []
        query = build_service_query(family, bbox)

        if query is not None:
            data = query_fn(query, f"service:{family['key']}")
            sub_labels = subcategory_labels(family)
            seen: set = set()

            for el in data.get("elements", []):
                tags = el.get("tags") or {}
                subcategory = classify_service_element(family, tags)

                if subcategory is None:
                    continue

                point = service_point(el)

                if point is None:
                    continue

                key = (el.get("type"), el.get("id"))
                if el.get("id") is not None and key in seen:
                    continue
                seen.add(key)

                items.append({
                    "id": el.get("id"),
                    "type": el.get("type"),
                    "name": tags.get("name") or "Néant",
                    "family": family["key"],
                    "familyLabel": family["label"],
                    "subcategory": subcategory,
                    "subcategoryLabel": sub_labels.get(subcategory, subcategory),
                    "sourceTag": source_tag(family, tags),
                    "point": point,
                    "tags": service_tags(tags),
                })

        services[family["key"]] = items

    return services


def write_service_layers(out_dir: Path, services: dict, generated_at: str, bbox: str) -> dict:
    reports_dir = out_dir / "reports"
    families_report = []

    for family in SERVICE_FAMILIES:
        items = services.get(family["key"], [])
        features = [service_point_feature(item) for item in items]
        relative_path = f"geojson/services/{family['key']}.geojson"
        write_geojson(out_dir / relative_path, features)

        sub_counts = {sub["key"]: 0 for sub in family["subcategories"]}
        for item in items:
            sub_counts[item["subcategory"]] = sub_counts.get(item["subcategory"], 0) + 1

        families_report.append({
            "key": family["key"],
            "label": family["label"],
            "implemented": bool(family.get("implemented")),
            "file": relative_path,
            "geometryType": "Point",
            "count": len(features),
            "subcategories": [
                {"key": sub["key"], "label": sub["label"], "count": sub_counts.get(sub["key"], 0)}
                for sub in family["subcategories"]
            ],
        })

    reports_dir.mkdir(parents=True, exist_ok=True)
    index = {
        "generatedAt": generated_at,
        "bbox": bbox,
        "bboxOrder": "south,west,north,east",
        "geometry": "Point (position du noeud, ou center Overpass pour way/relation)",
        "families": families_report,
    }
    (reports_dir / "services_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return index


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
    parser.add_argument(
        "--overpass-cache-dir",
        default=None,
        help=(
            "Cache de reprise Overpass. Par défaut : "
            "exports/.overpass-cache/<bundle_id>."
        ),
    )
    parser.add_argument(
        "--no-overpass-cache",
        action="store_true",
        help="Désactive le cache de reprise Overpass pour cette extraction.",
    )
    parser.add_argument(
        "--refresh-overpass-cache",
        action="store_true",
        help="Ignore les réponses en cache et les remplace après téléchargement.",
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

    project_root = Path(__file__).resolve().parent.parent
    if args.no_overpass_cache:
        overpass_cache_dir = None
    elif args.overpass_cache_dir:
        overpass_cache_dir = Path(args.overpass_cache_dir)
    else:
        cache_key = bundle_id or slugify_city(city)
        overpass_cache_dir = project_root / "exports" / ".overpass-cache" / cache_key

    def overpass_query(query: str, label: str) -> dict:
        return query_with_retry(
            query,
            label,
            cache_dir=overpass_cache_dir,
            refresh_cache=args.refresh_overpass_cache,
            split_bbox_on_failure=True,
        )

    queries = build_queries(bbox)

    print("CS2 Realmap Generator - extraction OpenStreetMap")
    print(f"Ville / zone : {city}")
    print(f"BBOX         : {bbox}")
    if args.bundle_output:
        print(f"Bundle ID    : {bundle_id}")
        print(f"Bundle root  : {args.bundle_root}")
    print(f"Pack exports : {pack_dir}")
    if overpass_cache_dir is not None:
        print(f"Cache reprise: {overpass_cache_dir}")
    print()

    print("[1/4] Construction de l’index de densité résidentielle...")
    bld_data = overpass_query(queries["buildings_levels"], "buildings_levels")
    building_index: dict[tuple[str, int], int] = {}

    for el in bld_data.get("elements", []):
        tags = el.get("tags") or {}
        lvl = parse_building_levels(tags.get("building:levels"))

        key = osm_element_key(el)
        if lvl > 0 and key is not None:
            building_index[key] = lvl

    print(f"      Index : {len(building_index)} bâtiments avec données d’étages\n")

    print("[2/4] Téléchargement des polygones de zonage...")
    zone_categories = ["residential", "commercial", "industrial", "retail", "parking", "office", "mixed"]
    raw: dict[str, list] = {}

    for cat in zone_categories:
        result = overpass_query(queries[cat], cat)
        raw[cat] = result.get("elements", [])
        print(f"      {cat}: {len(raw[cat])} éléments")

    print("\n[3/4] Téléchargement des routes, chemins et voies ferrées...")
    roads_data = overpass_query(build_roads_query(bbox), "roads")
    raw["roads"] = roads_data.get("elements", [])
    print(f"      roads: {len(raw['roads'])} éléments")
    paths_data = overpass_query(build_paths_query(bbox), "paths")
    raw["paths"] = paths_data.get("elements", [])
    print(f"      paths: {len(raw['paths'])} éléments")

    railways_data = overpass_query(build_railways_query(bbox), "railways")
    raw["railways"] = railways_data.get("elements", [])
    print(f"      railways: {len(raw['railways'])} éléments")

    water_lines_data = overpass_query(build_water_lines_query(bbox), "water_lines")
    raw["water_lines"] = water_lines_data.get("elements", [])
    print(f"      water_lines: {len(raw['water_lines'])} éléments")

    water_areas_data = overpass_query(build_water_areas_query(bbox), "water_areas")
    raw["water_areas"] = water_areas_data.get("elements", [])
    print(f"      water_areas: {len(raw['water_areas'])} éléments")

    print("\n[4/4] Classification des zones et couches linéaires...")

    output: dict[str, list] = {cat: [] for cat in zone_categories}
    output["roads"] = []
    output["paths"] = []
    output["railways"] = []
    output["water_lines"] = []
    output["water_areas"] = []
    skipped = 0
    skipped_roads = 0
    skipped_paths = 0
    skipped_railways = 0
    excluded_inactive_railways = 0
    skipped_water_lines = 0
    skipped_water_areas = 0
    # Un même objet OSM peut répondre à plusieurs requêtes (par exemple un
    # bâtiment mixed_use portant aussi shop=*).  La clé inclut le type OSM :
    # les identifiants node/way/relation ne partagent pas le même espace.
    commercial_ids: set[tuple[str, int]] = set()
    mixed_ids = {
        key
        for element in raw["mixed"]
        if (key := osm_element_key(element)) is not None and extract_coords(element)
    }
    retail_ids = {
        key
        for element in raw["retail"]
        if (key := osm_element_key(element)) is not None and extract_coords(element)
    }

    for el in raw["commercial"]:
        key = osm_element_key(el)
        if key in mixed_ids or key in retail_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        if key is not None:
            commercial_ids.add(key)

        zone = classify_commercial(tags)

        output["commercial"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": zone,
            "cs2": CS2_LABELS[f"com_{zone}"],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["residential"]:
        if osm_element_key(el) in mixed_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        zone = classify_residential(tags, building_index, osm_element_key(el))
        cs2_key = {"high": "res_high", "medium": "res_med", "low": "res_low"}[zone]

        output["residential"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": zone,
            "cs2": CS2_LABELS[cs2_key],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["industrial"]:
        if osm_element_key(el) in mixed_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["industrial"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": "industrial",
            "cs2": CS2_LABELS["industrial"],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["retail"]:
        if osm_element_key(el) in mixed_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["retail"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": "retail",
            "cs2": CS2_LABELS["retail"],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["parking"]:
        if osm_element_key(el) in mixed_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        zone = classify_parking(tags)

        output["parking"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": zone,
            "cs2": CS2_LABELS[f"prk_{zone}"],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["office"]:
        key = osm_element_key(el)
        if key in mixed_ids or key in commercial_ids:
            continue

        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["office"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": "office",
            "cs2": CS2_LABELS["office"],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["mixed"]:
        tags = el.get("tags") or {}
        coords = extract_coords(el)

        if not coords:
            skipped += 1
            continue

        output["mixed"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name", ""),
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "zone": "mixed",
            "cs2": CS2_LABELS["mixed"],
            "tags": extract_zone_tags(tags),
        })

    for el in raw["roads"]:
        tags = el.get("tags") or {}
        coords = extract_line_coords(el)

        if not coords:
            skipped_roads += 1
            continue

        classification = classify_road(tags)
        road_tags = extract_road_tags(tags)
        road_category = classify_road_category(tags)

        output["roads"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
            "name": tags.get("name") or "Néant",
            "category": "Roads",
            "subcategory": classification["subcategory"],
            "sourceTag": classification["sourceTag"],
            "confidence": classification["confidence"],
            "coords": coords,
            "tags": road_tags,
            "roadCategory": road_category,
            "roadColor": road_category_color(road_category),
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
            "osmType": el.get("type"),
            "name": tags.get("name") or "Néant",
            "category": "Paths",
            "subcategory": classification["subcategory"],
            "sourceTag": classification["sourceTag"],
            "confidence": classification["confidence"],
            "coords": coords,
            "tags": extract_path_tags(tags),
            "roadCategory": "pathway",
            "roadColor": road_category_color("pathway"),
        })

    for el in raw["railways"]:
        tags = el.get("tags") or {}

        if not is_active_railway(tags):
            excluded_inactive_railways += 1
            continue

        item = railway_item(el)
        if item is None:
            skipped_railways += 1
            continue

        output["railways"].append(item)

    for el in raw["water_lines"]:
        tags = el.get("tags") or {}
        coords = extract_line_coords(el)

        if not coords:
            skipped_water_lines += 1
            continue

        subtype = classify_water_line(tags)

        output["water_lines"].append({
            "id": el.get("id"),
            "osmType": el.get("type"),
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
            "osmType": el.get("type"),
            "name": tags.get("name") or "Néant",
            "category": "Water",
            "subcategory": subtype,
            "sourceTag": tags.get("water") or tags.get("natural") or tags.get("landuse") or tags.get("waterway") or "",
            "confidence": 1.0,
            "coords": coords,
            "polygonParts": extract_polygon_parts(el),
            "tags": extract_water_tags(tags),
        })

    total = sum(len(v) for v in output.values())
    res = output["residential"]
    com = output["commercial"]
    roads = output["roads"]
    paths = output["paths"]
    railways = output["railways"]

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
    print(f"  Voies ferrées récupérées   : {len(railways)}")
    print(f"  Lignes d’eau récupérées    : {len(output['water_lines'])}")
    print(f"  Zones d’eau récupérées     : {len(output['water_areas'])}")
    print(f"  Ignorés sans géométrie     : {skipped}")
    print(f"  Routes ignorées sans géom. : {skipped_roads}")
    print(f"  Chemins ignorés sans géom. : {skipped_paths}")
    print(f"  Voies ferrées sans géom.   : {skipped_railways}")
    print(f"  Voies ferrées inactives    : {excluded_inactive_railways}")
    print(f"  Lignes eau sans géom.      : {skipped_water_lines}")
    print(f"  Zones eau sans géom.       : {skipped_water_areas}")
    print(f"  TOTAL overlays hors services: {total}")

    print("\n[Services] Téléchargement des familles de services...")
    services = download_service_families(bbox, query_fn=overpass_query)
    for family_def in SERVICE_FAMILIES:
        service_count = len(services.get(family_def["key"], []))
        print(f"      {family_def['label']:<42}: {service_count}")

    service_feature_total = sum(len(items) for items in services.values())
    legacy_all_features_count = total - len(output["railways"])
    unique_osm_elements: set[tuple[str, int]] = set()
    for items in [*output.values(), *services.values()]:
        for item in items:
            item_id = item.get("id")
            item_type = item.get("osmType") or item.get("type")
            if item_id is not None and item_type:
                unique_osm_elements.add((str(item_type), int(item_id)))

    ts = datetime.now(timezone.utc).isoformat()

    split_report = {
        # `total` est conservé pour compatibilité : il exclut les services mais
        # inclut la source ferroviaire indépendante.
        "total": total,
        "overlayFeaturesWithoutServices": total,
        "legacyAllFeaturesCount": legacy_all_features_count,
        "independentRailwayFeatureCount": len(output["railways"]),
        "independentServiceFeatureCount": service_feature_total,
        "allBundleFeatureCount": total + service_feature_total,
        "uniqueOsmElementCount": len(unique_osm_elements),
        "skippedPolygonsWithoutGeometry": skipped,
        "skippedRoadsWithoutGeometry": skipped_roads,
        "skippedPathsWithoutGeometry": skipped_paths,
        "skippedRailwaysWithoutGeometry": skipped_railways,
        "excludedInactiveRailways": excluded_inactive_railways,
        "counts": {
            cat: len(output.get(cat, []))
            for cat in zone_categories + ["roads", "paths", "railways", "water_lines", "water_areas"]
        },
        "serviceCounts": {
            family["key"]: len(services.get(family["key"], []))
            for family in SERVICE_FAMILIES
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

    services_index = write_service_layers(
        out_dir=pack_dir,
        services=services,
        generated_at=ts,
        bbox=bbox,
    )
    service_total = sum(family["count"] for family in services_index["families"])
    print(f"\n  Services (points) récupérés : {service_total}")
    print(f"  Features du bundle          : {total + service_total}")
    print(f"  Objets OSM uniques          : {len(unique_osm_elements)}")

    print(f"\nPack GeoJSON scindé : {pack_dir}")


if __name__ == "__main__":
    main()
