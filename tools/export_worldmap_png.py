from __future__ import annotations

import argparse
import json
from pathlib import Path

from export_heightmap_from_dem import (
    arcgis_interpolation,
    bbox_from_center_size,
    build_export_url,
    download_dem_array_tiled,
    normalize_array_to_png,
    require_runtime_deps,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export CS2 worldmap relief PNG from USGS 3DEP DEM."
    )

    parser.add_argument("--center-lon", required=True)
    parser.add_argument("--center-lat", required=True)
    parser.add_argument("--size-km", required=True)
    parser.add_argument("--pixels", type=int, default=4096)
    parser.add_argument("--out-dir", default="exports")

    # Compatibilité avec l'ancien export tuiles web.
    # export_cs2_pngs.py envoie encore ces options.
    parser.add_argument("--provider", default=None)
    parser.add_argument("--zoom", default=None)

    parser.add_argument("--min-elev", type=float, default=None)
    parser.add_argument("--max-elev", type=float, default=None)

    parser.add_argument(
        "--worldmap-normalization",
        "--heightmap-normalization",
        dest="normalization",
        default="nonta-manual",
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
        "--worldmap-resampling",
        "--heightmap-resampling",
        dest="resampling",
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
    out_name = f"worldmap_{args.center_lon}_{args.center_lat}_{args.size_km}.png"
    out_png = out_dir / out_name

    print("=== EXPORT WORLDMAP DEM ===")
    print(f"centerLon : {args.center_lon}")
    print(f"centerLat : {args.center_lat}")
    print(f"sizeKm    : {args.size_km}")
    print(f"pixels    : {args.pixels}")
    print(f"tiles     : {args.tiles}x{args.tiles}")
    print(f"overlap   : {args.tile_overlap_px}px")
    print(f"resampling: {args.resampling}")
    print(f"norm      : {args.normalization}")
    print(f"bbox      : {bbox[1]:.6f},{bbox[0]:.6f},{bbox[3]:.6f},{bbox[2]:.6f}")
    print(f"output    : {out_png}")

    if args.provider or args.zoom:
        print("")
        print("[INFO] --provider / --zoom ignorés : worldmap est maintenant un export DEM relief, pas une tuile RGB.")

    if args.print_url:
        one_shot_url = build_export_url(
            bbox,
            args.pixels,
            args.pixels,
            interpolation=arcgis_interpolation(args.resampling),
        )
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
        resampling=args.resampling,
    )

    print("[2/3] Normalisation 16-bit PNG...")

    zmin, zmax = normalize_array_to_png(
        arr,
        out_png,
        args.min_elev,
        args.max_elev,
        args.valid_min_elev,
        args.valid_max_elev,
        args.normalization,
        args.cs2_base_level,
        args.cs2_elevation_scale,
        args.cs2_vertical_scale,
    )

    metadata = {
        "type": "worldmap",
        "source": "USGS 3DEP Elevation ImageServer",
        "centerLon": center_lon,
        "centerLat": center_lat,
        "sizeKm": size_km,
        "pixels": args.pixels,
        "tiles": args.tiles,
        "tileOverlapPixels": args.tile_overlap_px,
        "resampling": args.resampling,
        "tileBlend": "feather",
        "bbox": {
            "west": bbox[0],
            "south": bbox[1],
            "east": bbox[2],
            "north": bbox[3],
        },
        "normalization": {
            "mode": args.normalization,
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

