from __future__ import annotations

import argparse
import json
from pathlib import Path


def round_number(value: float, digits: int = 6) -> float:
    rounded = round(float(value), digits)
    if rounded == -0.0:
        return 0.0
    return rounded


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise le contrat vertical PNG heightmap vers manifest.json."
    )
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--heightmap-metadata", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--contract", default=None)

    args = parser.parse_args()

    bundle_root = Path(args.bundle_root).resolve()
    png_dir = bundle_root / "png"

    manifest_path = Path(args.manifest).resolve() if args.manifest else bundle_root / "manifest.json"

    if args.heightmap_metadata:
        heightmap_meta_path = Path(args.heightmap_metadata).resolve()
    else:
        candidates = sorted(png_dir.glob("heightmap_*.metadata.json"))
        if not candidates:
            raise FileNotFoundError(f"Aucune metadata heightmap trouvée dans {png_dir}")
        heightmap_meta_path = candidates[0]

    contract_path = Path(args.contract).resolve() if args.contract else None
    if contract_path is None:
        contracts = sorted(png_dir.glob("cs2_png_contract_*.json"))
        contract_path = contracts[0] if contracts else None

    manifest = load_json(manifest_path)
    heightmap_meta = load_json(heightmap_meta_path)

    meta_norm = heightmap_meta.get("normalization") or {}
    if not meta_norm:
        raise ValueError(f"normalization absente dans {heightmap_meta_path}")

    required = [
        "baseLevelMeters",
        "belowSeaReserveMeters",
        "seaLevelMeters",
        "encodedMinElevationMeters",
        "encodedMaxElevationMeters",
        "elevationScaleMeters",
        "verticalScale",
    ]

    missing = [key for key in required if key not in meta_norm]
    if missing:
        raise ValueError(f"Champs verticaux manquants dans metadata heightmap: {missing}")

    sea_level = float(meta_norm["seaLevelMeters"])
    encoded_min = float(meta_norm["encodedMinElevationMeters"])
    vertical_scale = float(meta_norm["verticalScale"])
    below_sea_reserve = float(meta_norm["belowSeaReserveMeters"])

    recommended_water_level = round_number(
        (sea_level - encoded_min) * vertical_scale,
        3,
    )

    manifest.setdefault("heightmap", {})
    manifest["heightmap"].setdefault("normalization", {})

    dst = manifest["heightmap"]["normalization"]

    for key in [
        "baseLevelMeters",
        "belowSeaReserveMeters",
        "seaLevelMeters",
        "encodedMinElevationMeters",
        "encodedMaxElevationMeters",
        "elevationScaleMeters",
        "verticalScale",
    ]:
        dst[key] = round_number(meta_norm[key], 6)

    manifest["heightmap"]["validMinElev"] = meta_norm.get(
        "inputValidMinElevationMeters",
        manifest["heightmap"].get("validMinElev"),
    )
    manifest["heightmap"]["validMaxElev"] = meta_norm.get(
        "inputValidMaxElevationMeters",
        manifest["heightmap"].get("validMaxElev"),
    )

    manifest["water"] = {
        "recommendedCs2WaterLevel": recommended_water_level,
        "waterReferenceElevationMeters": round_number(sea_level, 6),
        "belowSeaReserveMeters": round_number(below_sea_reserve, 6),
        "source": "computed-from-heightmap-normalization",
        "formula": "(seaLevelMeters - encodedMinElevationMeters) * verticalScale",
    }

    write_json(manifest_path, manifest)

    if contract_path and contract_path.exists():
        contract = load_json(contract_path)
        contract.setdefault("water", {})
        contract["water"] = dict(manifest["water"])
        write_json(contract_path, contract)

    print("Vertical contract synchronized.")
    print(f"bundleRoot                  : {bundle_root}")
    print(f"heightmapMetadata           : {heightmap_meta_path}")
    print(f"manifest                    : {manifest_path}")
    print(f"contract                    : {contract_path if contract_path else '[absent]'}")
    print(f"encodedMinElevationMeters   : {encoded_min}")
    print(f"seaLevelMeters              : {sea_level}")
    print(f"verticalScale               : {vertical_scale}")
    print(f"belowSeaReserveMeters       : {below_sea_reserve}")
    print(f"recommendedCs2WaterLevel    : {recommended_water_level}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
