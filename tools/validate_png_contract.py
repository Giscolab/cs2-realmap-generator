import argparse
import json
import math
import re
import struct
from pathlib import Path


DEFAULT_CENTER_LON = -117.7678
DEFAULT_CENTER_LAT = 33.666896
DEFAULT_WORLDMAP_SIZE_KM = 57.344
DEFAULT_HEIGHTMAP_SIZE_KM = 14.336
DEFAULT_PIXELS = 4096
CS2_TARGET_PLAYABLE_METERS = 14335.0

PNG_NAME_RE = re.compile(
    r"^(heightmap|worldmap)_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)\.png$",
    re.IGNORECASE,
)


def read_png_size(path: Path):
    with path.open("rb") as f:
        header = f.read(24)

    png_sig = b"\x89PNG\r\n\x1a\n"
    if len(header) < 24 or not header.startswith(png_sig):
        return None

    width, height = struct.unpack(">II", header[16:24])
    return width, height


def load_manifest(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))

    center = data.get("center") or {}
    world_map = data.get("worldMap") or {}
    heightmap = data.get("heightmap") or {}

    return {
        "center_lon": float(center.get("lon")),
        "center_lat": float(center.get("lat")),
        "worldmap_size_km": float(world_map.get("sizeKm")),
        "heightmap_size_km": float(heightmap.get("sizeKm")),
        "pixels": int(heightmap.get("pixels", DEFAULT_PIXELS)),
    }


def collect_pngs(roots):
    found = []

    for root in roots:
        root_path = Path(root).expanduser()
        if not root_path.exists():
            continue

        for path in root_path.rglob("*.png"):
            match = PNG_NAME_RE.match(path.name)
            if match:
                found.append(path)

    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def meters_delta(expected_lon, expected_lat, lon, lat):
    meters_per_degree_lat = 111_320.0
    center_lat_rad = math.radians(expected_lat)
    meters_per_degree_lon = meters_per_degree_lat * math.cos(center_lat_rad)

    dx = (lon - expected_lon) * meters_per_degree_lon
    dz = (lat - expected_lat) * meters_per_degree_lat

    return dx, dz


def check_file(path: Path, contract, center_tol_deg, size_tol_km):
    match = PNG_NAME_RE.match(path.name)
    if not match:
        return None

    kind = match.group(1).lower()
    lon = float(match.group(2))
    lat = float(match.group(3))
    size_km = float(match.group(4))

    expected_size = (
        contract["heightmap_size_km"]
        if kind == "heightmap"
        else contract["worldmap_size_km"]
    )

    expected_lon = contract["center_lon"]
    expected_lat = contract["center_lat"]

    size = read_png_size(path)
    width = size[0] if size else None
    height = size[1] if size else None

    dx_m, dz_m = meters_delta(expected_lon, expected_lat, lon, lat)
    world_scale = CS2_TARGET_PLAYABLE_METERS / (contract["heightmap_size_km"] * 1000.0)

    issues = []

    if abs(lon - expected_lon) > center_tol_deg:
        issues.append("lon")
    if abs(lat - expected_lat) > center_tol_deg:
        issues.append("lat")
    if abs(size_km - expected_size) > size_tol_km:
        issues.append("sizeKm")
    if width != contract["pixels"] or height != contract["pixels"]:
        issues.append("pixels")

    return {
        "path": path,
        "kind": kind,
        "lon": lon,
        "lat": lat,
        "size_km": size_km,
        "expected_size_km": expected_size,
        "width": width,
        "height": height,
        "dx_m": dx_m,
        "dz_m": dz_m,
        "dx_game_m": dx_m * world_scale,
        "dz_game_m": dz_m * world_scale,
        "issues": issues,
    }


def print_contract(contract):
    print("=== CONTRAT ATTENDU ===")
    print(f"centerLon={contract['center_lon']}")
    print(f"centerLat={contract['center_lat']}")
    print(f"worldmapSizeKm={contract['worldmap_size_km']}")
    print(f"heightmapSizeKm={contract['heightmap_size_km']}")
    print(f"pixels={contract['pixels']}")
    print()


def print_result(result):
    status = "OK" if not result["issues"] else "ERREUR"

    print(f"[{status}] {result['path']}")
    print(f"  type       : {result['kind']}")
    print(f"  center     : lon={result['lon']} lat={result['lat']}")
    print(f"  sizeKm     : {result['size_km']} attendu={result['expected_size_km']}")
    print(f"  pixels     : {result['width']}x{result['height']}")
    print(f"  delta réel : dx={result['dx_m']:.2f} m, dz={result['dz_m']:.2f} m")
    print(f"  delta jeu  : dx={result['dx_game_m']:.2f} m, dz={result['dz_game_m']:.2f} m")

    if result["issues"]:
        print("  problèmes  : " + ", ".join(result["issues"]))

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Valide que les PNG heightmap/worldmap correspondent au contrat CS2/TimelineMod."
    )

    parser.add_argument("--manifest", help="Manifest JSON CS2 Realmap / CityTimelineMod.")
    parser.add_argument("--center-lon", type=float, default=DEFAULT_CENTER_LON)
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--worldmap-size-km", type=float, default=DEFAULT_WORLDMAP_SIZE_KM)
    parser.add_argument("--heightmap-size-km", type=float, default=DEFAULT_HEIGHTMAP_SIZE_KM)
    parser.add_argument("--pixels", type=int, default=DEFAULT_PIXELS)
    parser.add_argument("--center-tol-deg", type=float, default=0.000001)
    parser.add_argument("--size-tol-km", type=float, default=0.001)
    parser.add_argument("--roots", nargs="+", default=["."], help="Dossiers à scanner.")
    parser.add_argument("--max-results", type=int, default=80)

    args = parser.parse_args()

    if args.manifest:
        contract = load_manifest(Path(args.manifest))
    else:
        contract = {
            "center_lon": args.center_lon,
            "center_lat": args.center_lat,
            "worldmap_size_km": args.worldmap_size_km,
            "heightmap_size_km": args.heightmap_size_km,
            "pixels": args.pixels,
        }

    print_contract(contract)

    pngs = collect_pngs(args.roots)

    if not pngs:
        print("Aucun PNG heightmap_*.png ou worldmap_*.png trouvé.")
        return 2

    bad = 0
    checked = 0

    for path in pngs[: args.max_results]:
        result = check_file(path, contract, args.center_tol_deg, args.size_tol_km)
        if not result:
            continue

        checked += 1
        if result["issues"]:
            bad += 1

        print_result(result)

    print("=== RÉSUMÉ ===")
    print(f"PNG vérifiés : {checked}")
    print(f"PNG invalides: {bad}")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

