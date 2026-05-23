from __future__ import annotations

import argparse
import io
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path


USGS_3DEP_EXPORT_IMAGE_URL = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/"
    "3DEPElevation/ImageServer/exportImage"
)


def require_runtime_deps():
    try:
        import numpy as np  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        print("[ERREUR] Dépendances manquantes.")
        print("Installe :")
        print("  python -m pip install pillow numpy")
        raise SystemExit(2)


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


def bbox_from_center_size(
    center_lon: float,
    center_lat: float,
    size_km: float,
) -> tuple[float, float, float, float]:
    half_m = size_km * 1000.0 / 2.0
    meters_lon, meters_lat = meters_per_degree(center_lat)

    dlon = half_m / meters_lon
    dlat = half_m / meters_lat

    return (
        center_lon - dlon,
        center_lat - dlat,
        center_lon + dlon,
        center_lat + dlat,
    )


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def split_sizes(total: int, parts: int) -> list[int]:
    base = total // parts
    remainder = total % parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]


def cumulative(values: list[int]) -> list[int]:
    out = [0]
    running = 0

    for value in values:
        running += value
        out.append(running)

    return out


def arcgis_interpolation(name: str) -> str:
    mapping = {
        "nearest": "RSP_NearestNeighbor",
        "bilinear": "RSP_BilinearInterpolation",
        "bicubic": "RSP_CubicConvolution",
    }
    return mapping.get(str(name).lower(), "RSP_BilinearInterpolation")


def build_export_url(
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
    interpolation: str = "RSP_BilinearInterpolation",
) -> str:
    params = {
        "bbox": ",".join(f"{v:.12f}" for v in bbox),
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": interpolation,
        "f": "image",
    }

    return USGS_3DEP_EXPORT_IMAGE_URL + "?" + urllib.parse.urlencode(params)


def download(url: str, retries: int = 4, timeout: int = 180) -> bytes:
    last_error: BaseException | None = None

    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "cs2-realmap-generator/heightmap-exporter"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()

            if not data.startswith((b"II", b"MM")):
                error_path = Path("dem_error_response.txt")
                error_path.write_bytes(data)
                raise RuntimeError(
                    "Réponse USGS non-TIFF. Réponse écrite dans dem_error_response.txt"
                )

            return data

        except urllib.error.HTTPError as exc:
            last_error = exc

            if exc.code not in {429, 500, 502, 503, 504}:
                raise

            print(f"      tentative {attempt}/{retries} échouée HTTP {exc.code}")

        except urllib.error.URLError as exc:
            last_error = exc
            print(f"      tentative {attempt}/{retries} échouée réseau : {exc}")

        if attempt < retries:
            time.sleep(min(2 * attempt, 8))

    raise RuntimeError(
        f"Téléchargement DEM impossible après {retries} tentatives: {last_error}"
    )


def read_tiff_as_array(tiff_bytes: bytes):
    import numpy as np
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None

    image = Image.open(BytesIO(tiff_bytes))
    arr = np.array(image, dtype=np.float32)

    if arr.ndim == 3:
        arr = arr[:, :, 0]

    return arr


def make_feather_weights(
    req_width: int,
    req_height: int,
    crop_x0: int,
    crop_y0: int,
    core_width: int,
    core_height: int,
):
    import numpy as np

    wx = np.ones(req_width, dtype=np.float32)
    wy = np.ones(req_height, dtype=np.float32)

    left = crop_x0
    right = req_width - (crop_x0 + core_width)
    top = crop_y0
    bottom = req_height - (crop_y0 + core_height)

    if left > 0:
        wx[:left] = np.linspace(0.0, 1.0, left, endpoint=False, dtype=np.float32)

    if right > 0:
        wx[-right:] = np.linspace(1.0, 0.0, right, endpoint=False, dtype=np.float32)

    if top > 0:
        wy[:top] = np.linspace(0.0, 1.0, top, endpoint=False, dtype=np.float32)

    if bottom > 0:
        wy[-bottom:] = np.linspace(1.0, 0.0, bottom, endpoint=False, dtype=np.float32)

    weights = wy[:, None] * wx[None, :]
    weights = np.maximum(weights, 0.0001)

    return weights


def download_dem_array_tiled(
    bbox: tuple[float, float, float, float],
    pixels: int,
    tiles: int,
    retries: int,
    keep_tiff_dir: Path | None,
    tile_overlap_px: int = 32,
    resampling: str = "bilinear",
):
    import numpy as np
    from PIL import Image

    west, south, east, north = bbox

    tile_overlap_px = max(0, int(tile_overlap_px))
    interpolation = arcgis_interpolation(resampling)

    col_sizes = split_sizes(pixels, tiles)
    row_sizes = split_sizes(pixels, tiles)
    col_edges = cumulative(col_sizes)
    row_edges = cumulative(row_sizes)

    accum = np.zeros((pixels, pixels), dtype=np.float64)
    weight_sum = np.zeros((pixels, pixels), dtype=np.float64)

    total_tiles = tiles * tiles
    index = 0

    for row in range(tiles):
        y0 = row_edges[row]
        y1 = row_edges[row + 1]
        height = y1 - y0

        for col in range(tiles):
            x0 = col_edges[col]
            x1 = col_edges[col + 1]
            width = x1 - x0

            req_x0 = max(0, x0 - tile_overlap_px)
            req_x1 = min(pixels, x1 + tile_overlap_px)
            req_y0 = max(0, y0 - tile_overlap_px)
            req_y1 = min(pixels, y1 + tile_overlap_px)

            req_width = req_x1 - req_x0
            req_height = req_y1 - req_y0

            lon_left = lerp(west, east, req_x0 / pixels)
            lon_right = lerp(west, east, req_x1 / pixels)
            lat_top = lerp(north, south, req_y0 / pixels)
            lat_bottom = lerp(north, south, req_y1 / pixels)

            tile_bbox = (lon_left, lat_bottom, lon_right, lat_top)
            index += 1

            print(
                f"      tuile {index:02d}/{total_tiles} "
                f"row={row + 1}/{tiles} col={col + 1}/{tiles} "
                f"core={width}x{height} request={req_width}x{req_height} "
                f"overlap={tile_overlap_px}px resampling={resampling} blend=feather"
            )

            url = build_export_url(
                tile_bbox,
                req_width,
                req_height,
                interpolation=interpolation,
            )
            tile_arr = None
            last_tile_error = None

            for tile_attempt in range(1, retries + 1):
                try:
                    tiff_bytes = download(url, retries=1)

                    if keep_tiff_dir is not None:
                        keep_tiff_dir.mkdir(parents=True, exist_ok=True)
                        tile_path = keep_tiff_dir / f"tile_r{row + 1:02d}_c{col + 1:02d}.tif"
                        tile_path.write_bytes(tiff_bytes)

                    with Image.open(io.BytesIO(tiff_bytes)) as img:
                        img.load()
                        tile_arr = np.array(img, dtype=np.float32)

                    break

                except (OSError, ValueError, RuntimeError) as exc:
                    last_tile_error = exc
                    print(
                        f"        lecture TIFF échouée {tile_attempt}/{retries} : {exc}"
                    )

                    if tile_attempt < retries:
                        time.sleep(min(2 * tile_attempt, 8))

            if tile_arr is None:
                print(
                    f"        [WARN] Lecture TIFF stricte impossible après {retries} tentatives."
                )
                print(
                    "        [WARN] Tentative de lecture tolérante Pillow LOAD_TRUNCATED_IMAGES."
                )

                try:
                    from PIL import ImageFile

                    previous_truncated_flag = ImageFile.LOAD_TRUNCATED_IMAGES
                    ImageFile.LOAD_TRUNCATED_IMAGES = True

                    try:
                        tiff_bytes = download(url, retries=1)

                        if keep_tiff_dir is not None:
                            keep_tiff_dir.mkdir(parents=True, exist_ok=True)
                            tile_path = keep_tiff_dir / f"tile_r{row + 1:02d}_c{col + 1:02d}_tolerant.tif"
                            tile_path.write_bytes(tiff_bytes)

                        with Image.open(io.BytesIO(tiff_bytes)) as img:
                            img.load()
                            tile_arr = np.array(img, dtype=np.float32)

                    finally:
                        ImageFile.LOAD_TRUNCATED_IMAGES = previous_truncated_flag

                except (OSError, ValueError, RuntimeError) as exc:
                    raise RuntimeError(
                        f"Tuile DEM TIFF illisible après {retries} tentatives strictes "
                        f"et fallback tolérant: {exc}"
                    ) from exc

            if tile_arr.ndim == 3:
                tile_arr = tile_arr[..., 0]

            if tile_arr.shape != (req_height, req_width):
                raise RuntimeError(
                    f"Taille DEM inattendue r{row + 1} c{col + 1}: "
                    f"attendu {(req_height, req_width)}, obtenu {tile_arr.shape}"
                )

            crop_x0 = x0 - req_x0
            crop_y0 = y0 - req_y0

            weights = make_feather_weights(
                req_width=req_width,
                req_height=req_height,
                crop_x0=crop_x0,
                crop_y0=crop_y0,
                core_width=width,
                core_height=height,
            )

            target = np.isfinite(tile_arr)

            accum_slice = accum[req_y0:req_y1, req_x0:req_x1]
            weight_slice = weight_sum[req_y0:req_y1, req_x0:req_x1]

            safe_weights = weights * target
            accum_slice += np.nan_to_num(tile_arr, nan=0.0).astype(np.float64) * safe_weights
            weight_slice += safe_weights

    full = np.empty((pixels, pixels), dtype=np.float32)
    valid = weight_sum > 0

    full[valid] = (accum[valid] / weight_sum[valid]).astype(np.float32)
    full[~valid] = np.nan

    return full


def normalize_array_to_png(
    arr,
    out_png: Path,
    explicit_min: float | None,
    explicit_max: float | None,
    valid_min: float,
    valid_max: float,
    normalization_mode: str = "local-minmax",
    base_level: float = 0.0,
    elevation_scale: float = 4096.0,
    vertical_scale: float = 1.0,
) -> tuple[float, float]:
    import numpy as np
    from PIL import Image

    mode = str(normalization_mode or "local-minmax").lower().replace("_", "-")
    valid = np.isfinite(arr) & (arr >= valid_min) & (arr <= valid_max)

    if not np.any(valid):
        raise RuntimeError("DEM vide ou sans pixels valides.")

    if mode == "nonta-manual":
        if elevation_scale <= 0:
            raise RuntimeError(f"elevation_scale invalide : {elevation_scale}")

        if vertical_scale <= 0:
            raise RuntimeError(f"vertical_scale invalide : {vertical_scale}")

        # Formule Nonta / Terraining :
        # png16 = ((elevationMeters - baseLevel) * verticalScale) / elevationScale * 65535
        zmin = float(base_level)
        zmax = zmin + float(elevation_scale) / float(vertical_scale)
        safe = np.where(valid, arr, zmin)
        norm = ((safe - zmin) * float(vertical_scale)) / float(elevation_scale)

    elif mode in ("absolute", "absolute-0-scale"):
        zmin = float(explicit_min) if explicit_min is not None else float(base_level)
        zmax = float(explicit_max) if explicit_max is not None else float(base_level) + float(elevation_scale)

        if zmax <= zmin:
            raise RuntimeError(f"Plage altitude invalide : min={zmin}, max={zmax}")

        safe = np.where(valid, arr, zmin)
        norm = (safe - zmin) / (zmax - zmin)

    else:
        # Mode historique : étire automatiquement le DEM local sur toute la plage 16-bit.
        zmin = float(explicit_min) if explicit_min is not None else float(np.min(arr[valid]))
        zmax = float(explicit_max) if explicit_max is not None else float(np.max(arr[valid]))

        if zmax <= zmin:
            raise RuntimeError(f"Plage altitude invalide : min={zmin}, max={zmax}")

        safe = np.where(valid, arr, zmin)
        norm = (safe - zmin) / (zmax - zmin)

    norm = np.clip(norm, 0.0, 1.0)
    out = np.rint(norm * 65535.0).astype(np.uint16)

    png = Image.fromarray(out, mode="I;16")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    png.save(out_png)

    return zmin, zmax


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export CS2 heightmap PNG from USGS 3DEP DEM."
    )

    parser.add_argument("--center-lon", required=True)
    parser.add_argument("--center-lat", required=True)
    parser.add_argument("--size-km", required=True)
    parser.add_argument("--pixels", type=int, default=4096)
    parser.add_argument("--out-dir", default="exports")
    parser.add_argument("--min-elev", type=float, default=None)
    parser.add_argument("--max-elev", type=float, default=None)
    parser.add_argument(
        "--heightmap-normalization",
        default="local-minmax",
        choices=("local-minmax", "nonta-manual", "absolute", "absolute-0-scale"),
        help="Mode d'encodage altitude -> PNG 16-bit.",
    )
    parser.add_argument("--cs2-base-level", type=float, default=1.0)
    parser.add_argument("--cs2-elevation-scale", type=float, default=4096.0)
    parser.add_argument("--cs2-vertical-scale", type=float, default=1.0)
    parser.add_argument("--valid-min-elev", type=float, default=-200)
    parser.add_argument("--valid-max-elev", type=float, default=5000)
    parser.add_argument("--tiles", type=int, default=4)
    parser.add_argument("--tile-overlap-px", type=int, default=128)
    parser.add_argument(
        "--heightmap-resampling",
        default="bilinear",
        choices=("nearest", "bilinear", "bicubic"),
    )
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--keep-tiff", action="store_true")
    parser.add_argument("--print-url", action="store_true")

    args = parser.parse_args()

    center_lon = float(args.center_lon)
    center_lat = float(args.center_lat)
    size_km = float(args.size_km)

    if args.pixels <= 0:
        raise SystemExit("[ERREUR] --pixels doit être positif.")

    if args.tiles <= 0:
        raise SystemExit("[ERREUR] --tiles doit être positif.")

    if args.tile_overlap_px < 0:
        raise SystemExit("[ERREUR] --tile-overlap-px doit être positif ou nul.")

    require_runtime_deps()

    bbox = bbox_from_center_size(center_lon, center_lat, size_km)

    out_dir = Path(args.out_dir)
    out_name = f"heightmap_{args.center_lon}_{args.center_lat}_{args.size_km}.png"
    out_png = out_dir / out_name

    print("=== EXPORT HEIGHTMAP DEM ===")
    print(f"centerLon : {args.center_lon}")
    print(f"centerLat : {args.center_lat}")
    print(f"sizeKm    : {args.size_km}")
    print(f"pixels    : {args.pixels}")
    print(f"tiles     : {args.tiles}x{args.tiles}")
    print(f"overlap   : {args.tile_overlap_px}px")
    print(f"resampling: {args.heightmap_resampling}")
    print(f"bbox      : {bbox[1]:.6f},{bbox[0]:.6f},{bbox[3]:.6f},{bbox[2]:.6f}")
    print(f"output    : {out_png}")

    if args.print_url:
        one_shot_url = build_export_url(bbox, args.pixels, args.pixels, interpolation=arcgis_interpolation(args.heightmap_resampling))
        print("")
        print("URL one-shot théorique:")
        print(one_shot_url)

    print("")
    print("[1/3] Téléchargement DEM USGS 3DEP par tuiles...")

    keep_tiff_dir = None

    if args.keep_tiff:
        keep_tiff_dir = out_png.with_suffix("")
        keep_tiff_dir = keep_tiff_dir.parent / f"{keep_tiff_dir.name}_tiles"

    arr = download_dem_array_tiled(
        bbox=bbox,
        pixels=args.pixels,
        tiles=args.tiles,
        retries=args.retries,
        keep_tiff_dir=keep_tiff_dir,
        tile_overlap_px=args.tile_overlap_px,
        resampling=args.heightmap_resampling,
    )

    print("[2/3] Normalisation 16-bit PNG...")

    zmin, zmax = normalize_array_to_png(
        arr,
        out_png,
        args.min_elev,
        args.max_elev,
        args.valid_min_elev,
        args.valid_max_elev,
        args.heightmap_normalization,
        args.cs2_base_level,
        args.cs2_elevation_scale,
        args.cs2_vertical_scale,
    )

    metadata = {
        "type": "heightmap",
        "source": "USGS 3DEP Elevation ImageServer",
        "centerLon": center_lon,
        "centerLat": center_lat,
        "sizeKm": size_km,
        "pixels": args.pixels,
        "tiles": args.tiles,
        "tileOverlapPixels": args.tile_overlap_px,
        "resampling": args.heightmap_resampling,
        "tileBlend": "feather",
        "bbox": {
            "west": bbox[0],
            "south": bbox[1],
            "east": bbox[2],
            "north": bbox[3],
        },
        "normalization": {
            "mode": args.heightmap_normalization,
            "inputValidMinElevationMeters": args.valid_min_elev,
            "inputValidMaxElevationMeters": args.valid_max_elev,
            "encodedMinElevationMeters": zmin,
            "encodedMaxElevationMeters": zmax,
            "baseLevelMeters": args.cs2_base_level,
            "elevationScaleMeters": args.cs2_elevation_scale,
            "verticalScale": args.cs2_vertical_scale,
            "minElevationMeters": zmin,
            "maxElevationMeters": zmax,
            "encoding": "uint16 grayscale PNG",
        },
    }

    metadata_path = out_png.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("[3/3] Terminé.")
    print(f"PNG      : {out_png}")
    print(f"Metadata : {metadata_path}")

    if keep_tiff_dir is not None:
        print(f"TIFFs    : {keep_tiff_dir}")

    print(f"Altitude : min={zmin:.3f} m / max={zmax:.3f} m")
    print(f"Filtre   : valid_min={args.valid_min_elev:.3f} m / valid_max={args.valid_max_elev:.3f} m")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

