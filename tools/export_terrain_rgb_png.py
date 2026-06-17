from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image


EARTH_RADIUS_M = 6378137.0
TILE_SIZE = 512


def lon_to_world_px(lon: float, zoom: int, tile_size: int = TILE_SIZE) -> float:
    return (lon + 180.0) / 360.0 * (2 ** zoom) * tile_size


def lat_to_world_px(lat: float, zoom: int, tile_size: int = TILE_SIZE) -> float:
    lat_rad = math.radians(lat)
    merc = math.log(math.tan(math.pi / 4.0 + lat_rad / 2.0))
    return (1.0 - merc / math.pi) / 2.0 * (2 ** zoom) * tile_size


def world_px_to_lon(x: float, zoom: int, tile_size: int = TILE_SIZE) -> float:
    return x / ((2 ** zoom) * tile_size) * 360.0 - 180.0


def world_px_to_lat(y: float, zoom: int, tile_size: int = TILE_SIZE) -> float:
    n = math.pi - 2.0 * math.pi * y / ((2 ** zoom) * tile_size)
    return math.degrees(math.atan(math.sinh(n)))


def bbox_from_center_size(center_lon: float, center_lat: float, size_km: float) -> tuple[float, float, float, float]:
    half_m = size_km * 1000.0 / 2.0
    dlat = math.degrees(half_m / EARTH_RADIUS_M)
    dlon = math.degrees(half_m / (EARTH_RADIUS_M * math.cos(math.radians(center_lat))))
    return (
        center_lon - dlon,
        center_lat - dlat,
        center_lon + dlon,
        center_lat + dlat,
    )


def terrain_rgb_to_height(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Formule Nonta / Terrain-RGB :
    # -10000 + R * 6553.6 + G * 25.6 + B * 0.1
    return -10000.0 + (r.astype(np.float32) * 6553.6) + (g.astype(np.float32) * 25.6) + (b.astype(np.float32) * 0.1)


def _redact_secrets(text) -> str:
    """Masque les clés API (key=, access_token=) dans un texte/URL avant log."""
    return re.sub(r"((?:key|access_token)=)[^&\s]+", r"\1***", str(text))


def build_tile_url(provider: str, zoom: int, x: int, y: int, token: str) -> str:
    provider = provider.lower()

    if provider == "maptiler":
        return f"https://api.maptiler.com/tiles/terrain-rgb-v2/{zoom}/{x}/{y}.webp?key={token}"

    if provider == "mapbox":
        return f"https://api.mapbox.com/v4/mapbox.mapbox-terrain-dem-v1/{zoom}/{x}/{y}@2x.pngraw?access_token={token}"

    raise ValueError(f"provider invalide : {provider}")


def fetch_bytes(url: str, retries: int = 4, timeout: int = 60) -> bytes:
    last_error: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "cs2-realmap-generator/terrain-rgb-exporter"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            print(f"      tentative {attempt}/{retries} échouée : {_redact_secrets(exc)}")

    raise RuntimeError(f"Téléchargement tuile impossible après {retries} tentatives : {_redact_secrets(last_error)}")


def fetch_tile_elevation(provider: str, zoom: int, x: int, y: int, token: str, retries: int) -> np.ndarray:
    url = build_tile_url(provider, zoom, x, y, token)
    data = fetch_bytes(url, retries=retries)

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGBA")
        arr = np.array(img, dtype=np.uint8)

    return terrain_rgb_to_height(arr[..., 0], arr[..., 1], arr[..., 2])


def resample_elevation_from_tiles(
    center_lon: float,
    center_lat: float,
    size_km: float,
    pixels: int,
    zoom: int,
    provider: str,
    token: str,
    retries: int,
) -> np.ndarray:
    west, south, east, north = bbox_from_center_size(center_lon, center_lat, size_km)

    x0 = lon_to_world_px(west, zoom)
    x1 = lon_to_world_px(east, zoom)
    y0 = lat_to_world_px(north, zoom)
    y1 = lat_to_world_px(south, zoom)

    tile_x0 = math.floor(x0 / TILE_SIZE)
    tile_x1 = math.floor(x1 / TILE_SIZE)
    tile_y0 = math.floor(y0 / TILE_SIZE)
    tile_y1 = math.floor(y1 / TILE_SIZE)

    tile_count_x = tile_x1 - tile_x0 + 1
    tile_count_y = tile_y1 - tile_y0 + 1

    print(f"bbox      : {south:.6f},{west:.6f},{north:.6f},{east:.6f}")
    print(f"zoom      : {zoom}")
    print(f"tiles     : x={tile_x0}..{tile_x1} ({tile_count_x}), y={tile_y0}..{tile_y1} ({tile_count_y})")

    mosaic = np.empty((tile_count_y * TILE_SIZE, tile_count_x * TILE_SIZE), dtype=np.float32)

    total = tile_count_x * tile_count_y
    index = 0

    for ty in range(tile_y0, tile_y1 + 1):
        for tx in range(tile_x0, tile_x1 + 1):
            index += 1
            wrapped_tx = tx % (2 ** zoom)

            print(f"      tuile {index:03d}/{total} z={zoom} x={wrapped_tx} y={ty}")
            tile = fetch_tile_elevation(provider, zoom, wrapped_tx, ty, token, retries)

            ox = (tx - tile_x0) * TILE_SIZE
            oy = (ty - tile_y0) * TILE_SIZE
            mosaic[oy:oy + TILE_SIZE, ox:ox + TILE_SIZE] = tile

    src_x0 = x0 - tile_x0 * TILE_SIZE
    src_y0 = y0 - tile_y0 * TILE_SIZE
    src_w = x1 - x0
    src_h = y1 - y0

    # Bilinear maison, volontairement simple et stable.
    xs = src_x0 + (np.arange(pixels, dtype=np.float64) + 0.5) * src_w / pixels
    ys = src_y0 + (np.arange(pixels, dtype=np.float64) + 0.5) * src_h / pixels

    xs = np.clip(xs, 0, mosaic.shape[1] - 2)
    ys = np.clip(ys, 0, mosaic.shape[0] - 2)

    x_floor = np.floor(xs).astype(np.int32)
    y_floor = np.floor(ys).astype(np.int32)

    x_frac = (xs - x_floor).astype(np.float32)
    y_frac = (ys - y_floor).astype(np.float32)

    out = np.empty((pixels, pixels), dtype=np.float32)

    for row in range(pixels):
        y = y_floor[row]
        fy = y_frac[row]

        a = mosaic[y, x_floor] * (1.0 - x_frac) + mosaic[y, x_floor + 1] * x_frac
        b = mosaic[y + 1, x_floor] * (1.0 - x_frac) + mosaic[y + 1, x_floor + 1] * x_frac

        out[row, :] = a * (1.0 - fy) + b * fy

    return out


CS2_DEFAULT_SEA_LEVEL = 511.7


def write_png16_nonta(
    arr: np.ndarray,
    out_png: Path,
    base_level: float,
    below_sea_reserve: float,
    elevation_scale: float,
    vertical_scale: float,
    valid_min: float,
    valid_max: float,
) -> tuple[float, float]:
    valid = np.isfinite(arr) & (arr >= valid_min) & (arr <= valid_max)

    if not np.any(valid):
        raise RuntimeError("Aucun pixel d'altitude valide.")

    reserve = max(0.0, float(below_sea_reserve))
    zmin = float(base_level) - reserve
    zmax = zmin + float(elevation_scale) / float(vertical_scale)

    safe = np.where(valid, arr, zmin)
    norm = ((safe - zmin) * float(vertical_scale)) / float(elevation_scale)
    norm = np.clip(norm, 0.0, 1.0)

    png_arr = np.rint(norm * 65535.0).astype(np.uint16)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(png_arr, mode="I;16").save(out_png)

    return zmin, zmax


def main() -> int:
    parser = argparse.ArgumentParser(description="Export CS2 PNG depuis Terrain RGB façon Nonta.")

    parser.add_argument("--center-lon", type=float, required=True)
    parser.add_argument("--center-lat", type=float, required=True)
    parser.add_argument("--size-km", type=float, required=True)
    parser.add_argument("--pixels", type=int, default=4096)
    parser.add_argument("--zoom", type=int, default=14)
    parser.add_argument("--provider", choices=("maptiler", "mapbox"), default="maptiler")
    parser.add_argument("--token", default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--retries", type=int, default=4)

    parser.add_argument("--cs2-base-level", type=float, default=1.0)
    parser.add_argument("--below-sea-reserve-meters", type=float, default=None)
    parser.add_argument("--cs2-elevation-scale", type=float, default=4096.0)
    parser.add_argument("--cs2-vertical-scale", type=float, default=1.0)
    parser.add_argument("--valid-min-elev", type=float, default=-200.0)
    parser.add_argument("--valid-max-elev", type=float, default=5000.0)

    args = parser.parse_args()

    if args.below_sea_reserve_meters is None:
        args.below_sea_reserve_meters = CS2_DEFAULT_SEA_LEVEL / args.cs2_vertical_scale

    token = args.token
    if not token:
        token = os.environ.get("MAPTILER_API_KEY") if args.provider == "maptiler" else os.environ.get("MAPBOX_TOKEN") or os.environ.get("PUBLIC_MAPBOX_TOKEN")

    if not token:
        raise SystemExit(
            "[ERREUR] Token manquant. Utilise --token ou la variable d'environnement MAPTILER_API_KEY / MAPBOX_TOKEN."
        )

    print("=== EXPORT TERRAIN RGB ===")
    print(f"provider  : {args.provider}")
    print(f"centerLon : {args.center_lon}")
    print(f"centerLat : {args.center_lat}")
    print(f"sizeKm    : {args.size_km}")
    print(f"pixels    : {args.pixels}")

    arr = resample_elevation_from_tiles(
        center_lon=args.center_lon,
        center_lat=args.center_lat,
        size_km=args.size_km,
        pixels=args.pixels,
        zoom=args.zoom,
        provider=args.provider,
        token=token,
        retries=args.retries,
    )

    out_png = Path(args.out)
    zmin, zmax = write_png16_nonta(
        arr=arr,
        out_png=out_png,
        base_level=args.cs2_base_level,
        below_sea_reserve=args.below_sea_reserve_meters,
        elevation_scale=args.cs2_elevation_scale,
        vertical_scale=args.cs2_vertical_scale,
        valid_min=args.valid_min_elev,
        valid_max=args.valid_max_elev,
    )

    metadata = {
        "type": "terrain-rgb-elevation",
        "source": args.provider,
        "centerLon": args.center_lon,
        "centerLat": args.center_lat,
        "sizeKm": args.size_km,
        "pixels": args.pixels,
        "zoom": args.zoom,
        "normalization": {
            "mode": "nonta-manual",
            "inputValidMinElevationMeters": args.valid_min_elev,
            "inputValidMaxElevationMeters": args.valid_max_elev,
            "belowSeaReserveMeters": args.below_sea_reserve_meters,
            "seaLevelMeters": args.cs2_base_level,
            "encodedMinElevationMeters": zmin,
            "encodedMaxElevationMeters": zmax,
            "baseLevelMeters": args.cs2_base_level,
            "elevationScaleMeters": args.cs2_elevation_scale,
            "verticalScale": args.cs2_vertical_scale,
            "encoding": "uint16 grayscale PNG",
        },
        "statsMeters": {
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "mean": float(np.nanmean(arr)),
        },
    }

    out_png.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("[OK] PNG      :", out_png)
    print("[OK] Metadata :", out_png.with_suffix(".metadata.json"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


