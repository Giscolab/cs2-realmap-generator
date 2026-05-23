from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from pathlib import Path


COUNTRY_CODE_ALIASES = {
    "france": "fr",
    "republique francaise": "fr",
    "république française": "fr",
    "china": "cn",
    "chine": "cn",
    "people_s_republic_of_china": "cn",
    "united states": "us",
    "united states of america": "us",
    "usa": "us",
    "us": "us",
    "etats unis": "us",
    "états unis": "us",
}


def round_number(value: float, digits: int) -> float:
    return round(float(value), digits)


def meters_per_degree(lat_deg: float) -> tuple[float, float]:
    lat = math.radians(lat_deg)

    meters_per_deg_lat = (
        111132.92
        - 559.82 * math.cos(2 * lat)
        + 1.175 * math.cos(4 * lat)
        - 0.0023 * math.cos(6 * lat)
    )

    meters_per_deg_lon = (
        111412.84 * math.cos(lat)
        - 93.5 * math.cos(3 * lat)
        + 0.118 * math.cos(5 * lat)
    )

    return meters_per_deg_lon, meters_per_deg_lat


def bbox_text_from_center_size(center_lon: float, center_lat: float, size_km: float) -> str:
    half_m = size_km * 1000.0 / 2.0
    meters_lon, meters_lat = meters_per_degree(center_lat)

    dlon = half_m / meters_lon
    dlat = half_m / meters_lat

    south = center_lat - dlat
    west = center_lon - dlon
    north = center_lat + dlat
    east = center_lon + dlon

    return f"{south:.6f},{west:.6f},{north:.6f},{east:.6f}"


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def slugify(value: str, fallback: str) -> str:
    ascii_value = strip_accents(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or fallback


def sanitize_bundle_id(value: str) -> str:
    normalized = strip_accents(value).lower()
    bundle_id = re.sub(r"[^a-z0-9_.-]+", "_", normalized).strip("_")
    bundle_id = re.sub(r"_+", "_", bundle_id)
    return bundle_id or "bundle"


def country_slug(country: str, country_code: str | None) -> str:
    if country_code:
        return slugify(country_code, "xx")

    key = slugify(country, "")
    if key in COUNTRY_CODE_ALIASES:
        return COUNTRY_CODE_ALIASES[key]

    return slugify(country, "xx")


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

    city_part = slugify(city, "city")
    country_part = country_slug(country, country_code)

    # Contract choisi : ville_pays_lat_lon.
    # Exemple : los_angeles_us_33.653495_-117.723999
    return f"{city_part}_{country_part}_{center_lat:.6f}_{center_lon:.6f}"


def ps_path(*parts: str) -> str:
    return ".\\" + "\\".join(part.strip("\\/") for part in parts if part.strip("\\/"))


def repo_posix_path(value: str) -> str:
    normalized = value.replace("\\", "/")

    if normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


CS2_DEFAULT_SEA_LEVEL = 511.7


def build_manifest(args: argparse.Namespace) -> dict:
    center_lon = round_number(args.center_lon, 6)
    center_lat = round_number(args.center_lat, 6)
    worldmap_km = round_number(args.worldmap_size_km, 3)
    heightmap_km = round_number(args.heightmap_size_km, 3)

    world_bbox = args.world_bbox or bbox_text_from_center_size(
        center_lon,
        center_lat,
        worldmap_km,
    )
    heightmap_bbox = args.heightmap_bbox or bbox_text_from_center_size(
        center_lon,
        center_lat,
        heightmap_km,
    )

    exports_root = args.exports_root.strip("\\/")
    city = args.city
    country = args.country
    country_code = args.country_code or None
    world_scale = 1.0

    if args.legacy_flat_output:
        suffix = f"{center_lon}_{center_lat}"

        png_dir = args.png_dir or ps_path(exports_root, f"png_{suffix}")
        geojson_dir = args.geojson_dir or ps_path(exports_root, f"geojson_{suffix}")

        bundle_id = args.bundle_id or suffix
        bundle_dir = ps_path(exports_root)
        bundle_index = ps_path(exports_root, "bundle_index.json")
        bundle_manifest = args.out or ps_path(
            exports_root,
            f"cs2_export_manifest_{suffix}.json",
        )
        timeline_config_path = ps_path(
            exports_root,
            "timeline_config.json",
        )
    else:
        bundle_root = args.bundle_root.strip("\\/")
        bundle_id = build_bundle_id(
            city=city,
            country=country,
            country_code=country_code,
            center_lon=center_lon,
            center_lat=center_lat,
            explicit_bundle_id=args.bundle_id,
        )

        bundle_dir = ps_path(bundle_root, bundle_id)
        bundle_index = args.bundle_index or ps_path(bundle_root, "bundle_index.json")

        png_dir = args.png_dir or ps_path(bundle_root, bundle_id, "png")
        geojson_dir = args.geojson_dir or ps_path(bundle_root, bundle_id, "geojson_pack")

        bundle_manifest = args.out or ps_path(
            bundle_root,
            bundle_id,
            "manifest.json",
        )

        timeline_config_path = args.timeline_config_out or ps_path(
            bundle_root,
            bundle_id,
            "timeline_config.json",
        )

    worldmap_name = f"worldmap_{center_lon}_{center_lat}_{worldmap_km}.png"
    heightmap_name = f"heightmap_{center_lon}_{center_lat}_{heightmap_km}.png"

    encoded_min_elevation_meters = round_number(
        args.cs2_base_level - args.below_sea_reserve_meters,
        6,
    )
    encoded_max_elevation_meters = round_number(
        args.cs2_base_level - args.below_sea_reserve_meters + args.cs2_elevation_scale / args.cs2_vertical_scale,
        6,
    )

    computed_recommended_cs2_water_level = round_number(
        (args.cs2_base_level - encoded_min_elevation_meters) * args.cs2_vertical_scale,
        6,
    )

    recommended_cs2_water_level = (
        args.recommended_cs2_water_level
        if args.recommended_cs2_water_level is not None
        else computed_recommended_cs2_water_level
    )

    return {
        "version": 2,
        "source": "cs2-realmap-generator",
        "kind": "cs2-export-bundle",
        "bundle": {
            "id": bundle_id,
            "city": city,
            "country": country,
            "countryCode": country_slug(country, country_code),
            "directory": bundle_dir,
            "recommendedCs2WaterLevel": recommended_cs2_water_level,
        },
        "city": city,
        "country": country,
        "center": {
            "lon": center_lon,
            "lat": center_lat,
        },
        "bboxOrder": "south,west,north,east",
        "worldMap": {
            "sizeKm": worldmap_km,
            "bbox": world_bbox,
        },
        "heightmap": {
            "sizeKm": heightmap_km,
            "bbox": heightmap_bbox,
            "pixels": args.pixels,
            "format": "PNG grayscale 16-bit",
            "validMinElev": args.valid_min_elev,
            "validMaxElev": args.valid_max_elev,
            "normalization": {
                "mode": args.heightmap_normalization,
                "baseLevelMeters": args.cs2_base_level,
                "belowSeaReserveMeters": args.below_sea_reserve_meters,
                "seaLevelMeters": args.cs2_base_level,
                "elevationScaleMeters": args.cs2_elevation_scale,
                "verticalScale": args.cs2_vertical_scale,
                "encodedMinElevationMeters": round_number(args.cs2_base_level - args.below_sea_reserve_meters, 3),
                "encodedMaxElevationMeters": round_number(
                    args.cs2_base_level - args.below_sea_reserve_meters + args.cs2_elevation_scale / args.cs2_vertical_scale,
                    6,
                ),
                "cs2HeightScale": args.cs2_elevation_scale,
            },
        },
        "water": {
            "recommendedCs2WaterLevel": recommended_cs2_water_level,
            "waterReferenceElevationMeters": args.cs2_base_level,
            "belowSeaReserveMeters": args.below_sea_reserve_meters,
            "source": "computed-from-heightmap-normalization",
            "targetCs2WaterLevel": CS2_DEFAULT_SEA_LEVEL,
            "formula": "(seaLevelMeters - encodedMinElevationMeters) * verticalScale",
        },
        "paths": {
            "bundleIndex": bundle_index,
            "bundleDir": bundle_dir,
            "bundleManifest": bundle_manifest,
            "pngDir": png_dir,
            "geojsonDir": geojson_dir,
            "timelineConfig": timeline_config_path,
            "worldmapPng": png_dir + "\\" + worldmap_name,
            "heightmapPng": png_dir + "\\" + heightmap_name,
        },
        "geojson": {
            "allFeatures": geojson_dir + "\\geojson\\all_features.geojson",
            "zoningPolygons": geojson_dir + "\\geojson\\zoning_polygons.geojson",
            "roads": geojson_dir + "\\geojson\\roads.geojson",
            "roadsMajor": geojson_dir + "\\geojson\\roads_major_clipped.geojson",
            "roadsDriveable": geojson_dir + "\\geojson\\roads_driveable_clipped.geojson",
            "paths": geojson_dir + "\\geojson\\paths.geojson",
            "waterLines": geojson_dir + "\\geojson\\water_lines_clipped.geojson",
            "waterAreas": geojson_dir + "\\geojson\\water_areas_clipped.geojson",
            "layerIndex": geojson_dir + "\\reports\\layer_index.json",
            "extractionReport": geojson_dir + "\\reports\\extraction_report.json",
        },
        "timelineMod": {
            "configPath": timeline_config_path,
            "useGeoJsonCenter": False,
            "originLon": center_lon,
            "originLat": center_lat,
            "worldOriginX": 0,
            "worldOriginZ": 0,
            "worldScale": world_scale,
            "overlayRotationDegrees": 0,
            "overlayScaleX": 1,
            "overlayScaleZ": 1,
            "flipX": False,
            "flipZ": False,
        },
        "expectedFiles": {
            "worldmapPng": worldmap_name,
            "heightmapPng": heightmap_name,
            "roadsMajorGeoJson": "roads_major_clipped.geojson",
            "roadsDriveableGeoJson": "roads_driveable_clipped.geojson",
            "waterLinesGeoJson": "water_lines_clipped.geojson",
            "waterAreasGeoJson": "water_areas_clipped.geojson",
        },
    }


def resolve_repo_path(repo_root: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")

    if normalized.startswith("./"):
        normalized = normalized[2:]

    return repo_root / normalized


def collect_referenced_paths(manifest: dict) -> list[str]:
    paths = [
        manifest["paths"]["pngDir"],
        manifest["paths"]["geojsonDir"],
        manifest["paths"]["worldmapPng"],
        manifest["paths"]["heightmapPng"],
        manifest["geojson"]["roadsMajor"],
        manifest["geojson"]["roadsDriveable"],
        manifest["geojson"]["waterLines"],
        manifest["geojson"]["waterAreas"],
        manifest["geojson"]["layerIndex"],
        manifest["geojson"]["extractionReport"],
    ]

    return paths


def check_existing(repo_root: Path, manifest: dict) -> int:
    missing = []

    for value in collect_referenced_paths(manifest):
        path = resolve_repo_path(repo_root, value)

        if not path.exists():
            missing.append(value)

    if not missing:
        print("[OK] Tous les fichiers principaux référencés existent.")
        return 0

    print("[ERREUR] Fichiers manquants :")

    for value in missing:
        print(f"  - {value}")

    return 1


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_bundle_index_entry(manifest: dict) -> dict:
    bundle = manifest["bundle"]
    bundle_id = bundle["id"]
    city = bundle.get("city") or ""
    country = bundle.get("country") or ""
    country_code = bundle.get("countryCode") or country_slug(country, None)
    water = manifest.get("water") or {}
    recommended_water_level = water.get("recommendedCs2WaterLevel", bundle.get("recommendedCs2WaterLevel"))

    display_parts = [part for part in (city, country_code.upper() if country_code else country) if part]
    display_name = ", ".join(display_parts) if display_parts else bundle_id

    return {
        "id": bundle_id,
        "displayName": display_name,
        "city": city,
        "country": country,
        "countryCode": country_code,
        "centerLon": manifest["center"]["lon"],
        "centerLat": manifest["center"]["lat"],
        "relativePath": bundle_id,
        "manifestPath": f"{bundle_id}/manifest.json",
        "bundlePath": bundle_id,
        "recommendedWaterLevel": recommended_water_level,
        "recommendedCs2WaterLevel": recommended_water_level,
        "worldmapSizeKm": manifest["worldMap"]["sizeKm"],
        "heightmapSizeKm": manifest["heightmap"]["sizeKm"],
    }

def write_bundle_index(repo_root: Path, manifest: dict) -> Path:
    index_path = resolve_repo_path(repo_root, manifest["paths"]["bundleIndex"])

    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[ERREUR] bundle_index.json invalide : {index_path} ({exc})") from exc
    else:
        data = {
            "schemaVersion": 1,
            "version": 1,
            "bundles": [],
        }

    bundles = data.get("bundles")
    if not isinstance(bundles, list):
        raise SystemExit(f"[ERREUR] Champ bundles invalide dans : {index_path}")

    entry = build_bundle_index_entry(manifest)

    by_id = {
        str(item.get("id")): item
        for item in bundles
        if isinstance(item, dict) and item.get("id") is not None
    }
    by_id[entry["id"]] = entry

    data["schemaVersion"] = 1
    data["version"] = 1
    data["bundles"] = sorted(
        by_id.values(),
        key=lambda item: (
            str(item.get("country", "")),
            str(item.get("city", "")),
            str(item.get("id", "")),
        ),
    )

    write_json(index_path, data)
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a CS2 export bundle manifest for a generated map center."
    )

    parser.add_argument("--center-lon", type=float, required=True)
    parser.add_argument("--center-lat", type=float, required=True)
    parser.add_argument("--city", default="Zone CS2")
    parser.add_argument("--country", default="")
    parser.add_argument("--country-code", default=None)
    parser.add_argument("--bundle-id", default=None)

    parser.add_argument("--worldmap-size-km", type=float, default=57.344)
    parser.add_argument("--heightmap-size-km", type=float, default=14.336)
    parser.add_argument("--pixels", type=int, default=4096)
    parser.add_argument("--tiles", type=int, default=4)
    parser.add_argument("--tile-overlap-px", type=int, default=128)
    parser.add_argument("--valid-min-elev", type=float, default=-200)
    parser.add_argument("--valid-max-elev", type=float, default=5000)
    parser.add_argument(
        "--heightmap-normalization",
        default="nonta-manual",
        choices=("local-minmax", "nonta-manual", "absolute", "absolute-0-scale"),
    )
    parser.add_argument("--cs2-base-level", type=float, default=1.0)
    parser.add_argument("--below-sea-reserve-meters", type=float, default=None)
    parser.add_argument("--cs2-elevation-scale", type=float, default=4096.0)
    parser.add_argument("--cs2-vertical-scale", type=float, default=1.0)
    parser.add_argument("--recommended-cs2-water-level", type=float, default=None)

    parser.add_argument("--world-bbox", default=None)
    parser.add_argument("--heightmap-bbox", default=None)

    parser.add_argument("--exports-root", default="exports")
    parser.add_argument("--bundle-root", default="exports/bundles")
    parser.add_argument("--bundle-index", default=None)
    parser.add_argument("--png-dir", default=None)
    parser.add_argument("--geojson-dir", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--timeline-config-out", default=None)

    parser.add_argument("--write-timeline-config", action="store_true")
    parser.add_argument("--skip-bundle-index", action="store_true")
    parser.add_argument("--legacy-flat-output", action="store_true")
    parser.add_argument("--check-existing", action="store_true")

    args = parser.parse_args()

    if args.below_sea_reserve_meters is None:
        args.below_sea_reserve_meters = CS2_DEFAULT_SEA_LEVEL / args.cs2_vertical_scale

    repo_root = Path(__file__).resolve().parents[1]
    manifest = build_manifest(args)

    out_path = resolve_repo_path(repo_root, manifest["paths"]["bundleManifest"])
    write_json(out_path, manifest)

    print("=== CS2 EXPORT BUNDLE MANIFEST ===")
    print(f"Bundle ID: {manifest['bundle']['id']}")
    print(f"Manifest : {out_path}")

    if args.write_timeline_config:
        timeline_config_path = resolve_repo_path(
            repo_root,
            manifest["timelineMod"]["configPath"],
        )

        timeline_config = dict(manifest["timelineMod"])
        timeline_config.pop("configPath", None)

        write_json(timeline_config_path, timeline_config)
        print(f"Timeline : {timeline_config_path}")

    if not args.skip_bundle_index and not args.legacy_flat_output:
        index_path = write_bundle_index(repo_root, manifest)
        print(f"Index    : {index_path}")

    if args.check_existing:
        return check_existing(repo_root, manifest)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


