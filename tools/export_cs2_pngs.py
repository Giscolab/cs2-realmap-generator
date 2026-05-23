from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path


COUNTRY_CODE_ALIASES = {
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


def load_contract(path: str | None) -> dict:
    if not path:
        return {}

    contract_path = Path(path)

    if not contract_path.exists():
        raise SystemExit(f"[ERREUR] Contrat introuvable : {contract_path}")

    return json.loads(contract_path.read_text(encoding="utf-8"))


def pick(
    args_value,
    contract: dict,
    keys: list[str],
    default=None,
    required: bool = False,
) -> str | None:
    if args_value is not None:
        return str(args_value)

    for key in keys:
        if key in contract and contract[key] is not None:
            return str(contract[key])

    if default is not None:
        return str(default)

    if required:
        raise SystemExit(f"[ERREUR] Valeur manquante. Clés attendues : {keys}")

    return None


def bool_pick(args_value: bool, contract: dict, keys: list[str], default: bool = False) -> bool:
    if args_value:
        return True

    for key in keys:
        if key in contract:
            return bool(contract[key])

    return default


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
    city: str | None,
    country: str | None,
    country_code: str | None,
    center_lon: str,
    center_lat: str,
    explicit_bundle_id: str | None,
) -> str:
    if explicit_bundle_id:
        return sanitize_bundle_id(explicit_bundle_id)

    city_part = slugify(city or "Zone CS2", "city")
    country_part = country_slug(country or "", country_code)

    return f"{city_part}_{country_part}_{float(center_lat):.6f}_{float(center_lon):.6f}"


def run_command(cmd: list[str], cwd: Path, dry_run: bool) -> None:
    print("")
    print(" ".join(cmd))

    if dry_run:
        return

    completed = subprocess.run(cmd, cwd=cwd)

    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


CS2_DEFAULT_SEA_LEVEL = 511.7


def write_resolved_contract(
    out_dir: Path,
    center_lon: str,
    center_lat: str,
    worldmap_size_km: str,
    heightmap_size_km: str,
    pixels: str,
    provider: str,
    zoom: str,
    tiles: str,
    tile_overlap_px: str,
        valid_min_elev: str,
    valid_max_elev: str,
    heightmap_normalization: str,
    cs2_base_level: str,
    below_sea_reserve_meters: str,
    cs2_elevation_scale: str,
    cs2_vertical_scale: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / f"cs2_png_contract_{center_lon}_{center_lat}.json"

    data = {
        "centerLon": float(center_lon),
        "centerLat": float(center_lat),
        "worldmapSizeKm": float(worldmap_size_km),
        "heightmapSizeKm": float(heightmap_size_km),
        "pixels": int(pixels),
        "worldmap": {
            "provider": provider,
            "zoom": int(zoom),
            "filename": f"worldmap_{center_lon}_{center_lat}_{worldmap_size_km}.png",
        },
        "heightmap": {
            "source": "MapTiler Terrain RGB",
            "tiles": int(tiles),
            "tileOverlapPixels": int(tile_overlap_px),
            "tileBlend": "feather",
            "validMinElev": float(valid_min_elev),
            "validMaxElev": float(valid_max_elev),
            "normalization": {
                "mode": heightmap_normalization,
                "baseLevelMeters": float(cs2_base_level),
                "belowSeaReserveMeters": float(below_sea_reserve_meters),
                "seaLevelMeters": float(cs2_base_level),
                "elevationScaleMeters": float(cs2_elevation_scale),
                "verticalScale": float(cs2_vertical_scale),
                "encodedMinElevationMeters": float(cs2_base_level) - float(below_sea_reserve_meters),
                "encodedMaxElevationMeters": float(cs2_base_level) - float(below_sea_reserve_meters) + float(cs2_elevation_scale) / float(cs2_vertical_scale),
                "cs2HeightScale": float(cs2_elevation_scale),
            },
            "filename": f"heightmap_{center_lon}_{center_lat}_{heightmap_size_km}.png",
        },
    }

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export CS2 worldmap + heightmap PNGs and validate their contract."
    )

    parser.add_argument("--contract", default=None)

    parser.add_argument("--bundle-output", action="store_true")
    parser.add_argument("--bundle-root", default=None)
    parser.add_argument("--bundle-id", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--country", default=None)
    parser.add_argument("--country-code", default=None)

    parser.add_argument("--center-lon", default=None)
    parser.add_argument("--center-lat", default=None)
    parser.add_argument("--worldmap-size-km", default=None)
    parser.add_argument("--heightmap-size-km", default=None)
    parser.add_argument("--pixels", default=None)

    parser.add_argument("--out-dir", default=None)

    parser.add_argument("--provider", default=None)
    parser.add_argument("--zoom", default=None)

    parser.add_argument("--tiles", default=None)
    parser.add_argument("--tile-overlap-px", default=None)
    parser.add_argument("--valid-min-elev", default=None)
    parser.add_argument("--valid-max-elev", default=None)
    parser.add_argument("--heightmap-normalization", default=None)
    parser.add_argument("--cs2-base-level", default=None)
    parser.add_argument("--below-sea-reserve-meters", default=None)
    parser.add_argument("--cs2-elevation-scale", default=None)
    parser.add_argument("--cs2-vertical-scale", default=None)
    parser.add_argument("--min-elev", default=None)
    parser.add_argument("--max-elev", default=None)

    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    parser.add_argument("--skip-worldmap", action="store_true")
    parser.add_argument("--skip-heightmap", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")

    args = parser.parse_args()

    contract = load_contract(args.contract)

    center_lon = pick(
        args.center_lon,
        contract,
        ["centerLon", "center_lون", "center_lon", "lon", "longitude"],
        required=True,
    )
    center_lat = pick(
        args.center_lat,
        contract,
        ["centerLat", "center_lat", "lat", "latitude"],
        required=True,
    )
    worldmap_size_km = pick(
        args.worldmap_size_km,
        contract,
        ["worldmapSizeKm", "worldmap_size_km", "worldmapKm"],
        default="57.344",
    )
    heightmap_size_km = pick(
        args.heightmap_size_km,
        contract,
        ["heightmapSizeKm", "heightmap_size_km", "heightmapKm"],
        default="14.336",
    )
    pixels = pick(
        args.pixels,
        contract,
        ["pixels", "sizePx", "resolution"],
        default="4096",
    )

    out_dir_str = pick(
        args.out_dir,
        contract,
        ["outDir", "out_dir", "exportsDir"],
        default="exports",
    )

    contract_bundle = contract.get("bundle", {}) if isinstance(contract.get("bundle"), dict) else {}

    bundle_root_str = pick(
        args.bundle_root,
        contract,
        ["bundleRoot", "bundle_root"],
        default="exports/bundles",
    )
    bundle_id = pick(
        args.bundle_id,
        contract_bundle,
        ["id", "bundleId", "bundle_id"],
        default=None,
    )
    city = pick(
        args.city,
        contract_bundle,
        ["city"],
        default=None,
    )
    country = pick(
        args.country,
        contract_bundle,
        ["country"],
        default=None,
    )
    country_code = pick(
        args.country_code,
        contract_bundle,
        ["countryCode", "country_code"],
        default=None,
    )

    if args.bundle_output:
        bundle_id = build_bundle_id(
            city=city,
            country=country,
            country_code=country_code,
            center_lon=center_lon,
            center_lat=center_lat,
            explicit_bundle_id=bundle_id,
        )
        out_dir_str = f"{bundle_root_str.strip('\\/')}/{bundle_id}/png"

    provider = pick(
        args.provider,
        contract,
        ["provider", "worldmapProvider"],
        default="maptiler",
    )
    zoom = pick(
        args.zoom,
        contract,
        ["zoom", "worldmapZoom"],
        default="14",
    )

    tiles = pick(
        args.tiles,
        contract,
        ["tiles", "heightmapTiles"],
        default="4",
    )
    tile_overlap_px = pick(
        args.tile_overlap_px,
        contract,
        ["tileOverlapPixels", "tile_overlap_px", "heightmapTileOverlapPixels"],
        default="128",
    )
    valid_min_elev = pick(
        args.valid_min_elev,
        contract,
        ["validMinElev", "valid_min_elev"],
        default="-200",
    )
    valid_max_elev = pick(
        args.valid_max_elev,
        contract,
        ["validMaxElev", "valid_max_elev"],
        default="5000",
    )
    min_elev = pick(
        args.min_elev,
        contract,
        ["minElev", "min_elev"],
        default=None,
    )
    max_elev = pick(
        args.max_elev,
        contract,
        ["maxElev", "max_elev"],
        default=None,
    )


    repo_root = Path(__file__).resolve().parents[1]
    tools_dir = repo_root / "tools"
    out_dir = repo_root / out_dir_str

    worldmap_png = out_dir / f"worldmap_{center_lon}_{center_lat}_{worldmap_size_km}.png"
    heightmap_png = out_dir / f"heightmap_{center_lon}_{center_lat}_{heightmap_size_km}.png"

    heightmap_normalization = pick(
        args.heightmap_normalization,
        contract.get("heightmap", {}) if isinstance(contract.get("heightmap"), dict) else contract,
        ["heightmapNormalization", "normalizationMode", "mode"],
        default="nonta-manual",
    )
    cs2_base_level = pick(
        args.cs2_base_level,
        contract.get("heightmap", {}).get("normalization", {}) if isinstance(contract.get("heightmap"), dict) else contract,
        ["baseLevelMeters", "baseLevel", "cs2BaseLevel"],
        default="1.000",
    )
    below_sea_reserve_meters = pick(
        args.below_sea_reserve_meters,
        contract.get("heightmap", {}).get("normalization", {}) if isinstance(contract.get("heightmap"), dict) else contract,
        ["belowSeaReserveMeters", "belowSeaReserve", "below_sea_reserve_meters"],
        default=None,
    )

    cs2_elevation_scale = pick(
        args.cs2_elevation_scale,
        contract.get("heightmap", {}).get("normalization", {}) if isinstance(contract.get("heightmap"), dict) else contract,
        ["elevationScaleMeters", "elevationScale", "cs2ElevationScale"],
        default="4096",
    )
    cs2_vertical_scale = pick(
        args.cs2_vertical_scale,
        contract.get("heightmap", {}).get("normalization", {}) if isinstance(contract.get("heightmap"), dict) else contract,
        ["verticalScale", "cs2VerticalScale"],
        default="1.0",
    )

    if below_sea_reserve_meters is None:
        below_sea_reserve_meters = str(round(CS2_DEFAULT_SEA_LEVEL / float(cs2_vertical_scale), 6))

    resolved_contract_path = write_resolved_contract(
        out_dir=out_dir,
        center_lon=center_lon,
        center_lat=center_lat,
        worldmap_size_km=worldmap_size_km,
        heightmap_size_km=heightmap_size_km,
        pixels=pixels,
        provider=provider,
        zoom=zoom,
        tiles=tiles,
        tile_overlap_px=tile_overlap_px,
        valid_min_elev=valid_min_elev,
        valid_max_elev=valid_max_elev,
        heightmap_normalization=heightmap_normalization,
        cs2_base_level=cs2_base_level,
        below_sea_reserve_meters=below_sea_reserve_meters,
        cs2_elevation_scale=cs2_elevation_scale,
        cs2_vertical_scale=cs2_vertical_scale,
    )

    print("=== CS2 PNG PIPELINE ===")
    print(f"contract          : {resolved_contract_path}")
    print(f"centerLon         : {center_lon}")
    print(f"centerLat         : {center_lat}")
    print(f"worldmapSizeKm    : {worldmap_size_km}")
    print(f"heightmapSizeKm   : {heightmap_size_km}")
    print(f"pixels            : {pixels}")
    print(f"outDir            : {out_dir}")
    if args.bundle_output:
        print(f"bundleID          : {bundle_id}")
        print(f"bundleRoot        : {bundle_root_str}")
    print(f"worldmap expected : {worldmap_png}")
    print(f"heightmap expected: {heightmap_png}")
    print(f"heightmap tiles   : {tiles}")
    print(f"heightmap overlap : {tile_overlap_px}px")
    print(f"heightmap norm    : {heightmap_normalization}")
    print(f"heightmap base    : {cs2_base_level}")
    print(f"below sea reserve : {below_sea_reserve_meters}")
    print(f"heightmap elevScale: {cs2_elevation_scale}")
    print(f"heightmap vertScale: {cs2_vertical_scale}")

    if not args.skip_worldmap:
        if worldmap_png.exists() and not args.force:
            print("")
            print(f"[SKIP] Worldmap existe déjà : {worldmap_png}")
        else:
            print("")
            print("[1/3] Export worldmap")

            cmd = [
                sys.executable,
                str(tools_dir / "export_terrain_rgb_png.py"),
                "--provider", provider,
                "--center-lon", center_lon,
                "--center-lat", center_lat,
                "--size-km", worldmap_size_km,
                "--pixels", pixels,
                "--zoom", zoom,
                "--out", str(worldmap_png),
                "--cs2-base-level", cs2_base_level,
                "--below-sea-reserve-meters", below_sea_reserve_meters,
                "--cs2-elevation-scale", cs2_elevation_scale,
                "--cs2-vertical-scale", cs2_vertical_scale,
                "--valid-min-elev", valid_min_elev,
                "--valid-max-elev", valid_max_elev,
            ]

            run_command(cmd, cwd=repo_root, dry_run=args.dry_run)
    else:
        print("")
        print("[SKIP] Worldmap désactivée.")

    if not args.skip_heightmap:
        if heightmap_png.exists() and not args.force:
            print("")
            print(f"[SKIP] Heightmap existe déjà : {heightmap_png}")
        else:
            print("")
            print("[2/3] Export heightmap")

            cmd = [
                sys.executable,
                str(tools_dir / "export_terrain_rgb_png.py"),
                "--provider", provider,
                "--center-lon", center_lon,
                "--center-lat", center_lat,
                "--size-km", heightmap_size_km,
                "--pixels", pixels,
                "--zoom", zoom,
                "--out", str(heightmap_png),
                "--cs2-base-level", cs2_base_level,
                "--below-sea-reserve-meters", below_sea_reserve_meters,
                "--cs2-elevation-scale", cs2_elevation_scale,
                "--cs2-vertical-scale", cs2_vertical_scale,
                "--valid-min-elev", valid_min_elev,
                "--valid-max-elev", valid_max_elev,
            ]

            run_command(cmd, cwd=repo_root, dry_run=args.dry_run)
    else:
        print("")
        print("[SKIP] Heightmap désactivée.")

    if not args.skip_validation:
        print("")
        print("[3/3] Validation contrat PNG")

        cmd = [
            sys.executable,
            str(tools_dir / "validate_png_contract.py"),
            "--roots", out_dir_str,
            "--center-lon", center_lon,
            "--center-lat", center_lat,
            "--worldmap-size-km", worldmap_size_km,
            "--heightmap-size-km", heightmap_size_km,
            "--pixels", pixels,
        ]

        run_command(cmd, cwd=repo_root, dry_run=args.dry_run)
    else:
        print("")
        print("[SKIP] Validation désactivée.")

    print("")
    print("=== PIPELINE TERMINÉ ===")
    print(f"worldmap : {worldmap_png}")
    print(f"heightmap: {heightmap_png}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

