#!/usr/bin/env python3
"""Construit et publie un bundle CS2 complet avec une seule commande.

Le script ne réimplémente aucune étape métier. Il orchestre les outils du dépôt
avec le même interpréteur Python, sans shell, puis ne synchronise le bundle vers
CityTimelineMod qu'après les validations PNG et GeoJSON.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, MutableMapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
EXTRACTOR = ROOT / "src" / "extract_zoning.py"
DEFAULT_BUNDLE_ROOT = Path("exports/bundles")


class PipelineError(RuntimeError):
    """Erreur de configuration ou d'exécution du pipeline complet."""


@dataclass(frozen=True)
class PipelineStep:
    key: str
    label: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class BundleBuildConfig:
    city: str
    country: str
    country_code: str
    bundle_id: str
    bbox: str
    heightmap_bbox: str
    center_lon: float
    center_lat: float
    worldmap_size_km: float = 57.344
    heightmap_size_km: float = 14.336
    pixels: int = 4096
    provider: str = "maptiler"
    zoom: int = 14
    tiles: int = 4
    tile_overlap_px: int = 128
    heightmap_normalization: str = "nonta-manual"
    cs2_base_level: float = 1.0
    below_sea_reserve_meters: float = 511.7
    cs2_elevation_scale: float = 4096.0
    cs2_vertical_scale: float = 1.0
    valid_min_elev: float = -200.0
    valid_max_elev: float = 5000.0
    min_elev: float | None = None
    max_elev: float | None = None
    recommended_cs2_water_level: float | None = None
    bundle_root: Path = DEFAULT_BUNDLE_ROOT
    overpass_cache_dir: Path | None = None
    no_overpass_cache: bool = False
    refresh_overpass_cache: bool = False
    terrain_token_env: str | None = None
    prompt_terrain_token: bool = False
    target_root: Path | None = None
    no_sync: bool = False
    allow_running_game: bool = False
    force_png: bool = False
    dry_run: bool = False


def _number(value: float | int) -> str:
    return str(value)


def _parse_bbox(value: str, label: str) -> tuple[float, float, float, float]:
    try:
        parts = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise PipelineError(
            f"{label} doit contenir quatre nombres : sud,ouest,nord,est."
        ) from exc
    if len(parts) != 4:
        raise PipelineError(
            f"{label} doit contenir quatre nombres : sud,ouest,nord,est."
        )
    south, west, north, east = parts
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise PipelineError(f"{label} est hors limites ou mal ordonnée : {value}")
    return south, west, north, east


def validate_config(config: BundleBuildConfig) -> None:
    world_bbox = _parse_bbox(config.bbox, "--bbox")
    height_bbox = _parse_bbox(config.heightmap_bbox, "--heightmap-bbox")

    if not (-180 <= config.center_lon <= 180 and -90 <= config.center_lat <= 90):
        raise PipelineError("Le centre géographique est hors limites.")
    for label, bbox in (("--bbox", world_bbox), ("--heightmap-bbox", height_bbox)):
        south, west, north, east = bbox
        if not (west <= config.center_lon <= east and south <= config.center_lat <= north):
            raise PipelineError(f"Le centre doit être inclus dans {label}.")

    if config.worldmap_size_km <= 0 or config.heightmap_size_km <= 0:
        raise PipelineError("Les tailles worldmap et heightmap doivent être positives.")
    if config.pixels <= 0 or config.tiles <= 0 or config.tile_overlap_px < 0:
        raise PipelineError("Pixels, tuiles et recouvrement PNG sont invalides.")
    if config.valid_min_elev >= config.valid_max_elev:
        raise PipelineError("--valid-min-elev doit être inférieur à --valid-max-elev.")
    if config.min_elev is not None and config.max_elev is not None:
        if config.min_elev >= config.max_elev:
            raise PipelineError("--min-elev doit être inférieur à --max-elev.")
    if config.cs2_elevation_scale <= 0 or config.cs2_vertical_scale <= 0:
        raise PipelineError("Les échelles d'élévation CS2 doivent être positives.")
    if config.below_sea_reserve_meters < 0:
        raise PipelineError("--below-sea-reserve-meters ne peut pas être négatif.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", config.bundle_id):
        raise PipelineError(
            "--bundle-id ne peut contenir que lettres, chiffres, point, tiret et underscore."
        )
    if not config.country_code.strip():
        raise PipelineError("--country-code ne peut pas être vide.")
    if config.bundle_root.is_absolute() or ".." in config.bundle_root.parts:
        raise PipelineError("--bundle-root doit rester relatif à la racine du dépôt.")
    if config.no_overpass_cache and config.overpass_cache_dir is not None:
        raise PipelineError(
            "--no-overpass-cache et --overpass-cache-dir sont incompatibles."
        )
    if config.no_overpass_cache and config.refresh_overpass_cache:
        raise PipelineError(
            "--no-overpass-cache et --refresh-overpass-cache sont incompatibles."
        )
    if config.no_sync and config.allow_running_game:
        raise PipelineError("--allow-running-game est inutile avec --no-sync.")


def build_pipeline(config: BundleBuildConfig) -> list[PipelineStep]:
    """Construit les commandes, sans exécuter ni accéder au réseau."""

    validate_config(config)
    python = sys.executable
    bundle_root = str(config.bundle_root)
    bundle_dir = (ROOT / config.bundle_root / config.bundle_id).resolve()
    png_dir = bundle_dir / "png"
    bundle_index = (ROOT / config.bundle_root / "bundle_index.json").resolve()

    extraction = [
        python,
        str(EXTRACTOR),
        "--city", config.city,
        "--country", config.country,
        "--country-code", config.country_code,
        f"--bbox={config.bbox}",
        "--bundle-output",
        "--bundle-root", bundle_root,
        "--bundle-id", config.bundle_id,
        "--split-layers",
    ]
    if config.no_overpass_cache:
        extraction.append("--no-overpass-cache")
    elif config.overpass_cache_dir is not None:
        extraction.extend(("--overpass-cache-dir", str(config.overpass_cache_dir)))
    if config.refresh_overpass_cache:
        extraction.append("--refresh-overpass-cache")

    png_export = [
        python,
        str(TOOLS / "export_cs2_pngs.py"),
        "--center-lon", _number(config.center_lon),
        "--center-lat", _number(config.center_lat),
        "--worldmap-size-km", _number(config.worldmap_size_km),
        "--heightmap-size-km", _number(config.heightmap_size_km),
        "--pixels", _number(config.pixels),
        "--bundle-output",
        "--bundle-root", bundle_root,
        "--bundle-id", config.bundle_id,
        "--city", config.city,
        "--country", config.country,
        "--country-code", config.country_code,
        "--provider", config.provider,
        "--zoom", _number(config.zoom),
        "--tiles", _number(config.tiles),
        "--tile-overlap-px", _number(config.tile_overlap_px),
        "--heightmap-normalization", config.heightmap_normalization,
        "--cs2-base-level", _number(config.cs2_base_level),
        "--below-sea-reserve-meters", _number(config.below_sea_reserve_meters),
        "--cs2-elevation-scale", _number(config.cs2_elevation_scale),
        "--cs2-vertical-scale", _number(config.cs2_vertical_scale),
        "--valid-min-elev", _number(config.valid_min_elev),
        "--valid-max-elev", _number(config.valid_max_elev),
        # La validation est exécutée après le manifeste par l'orchestrateur.
        "--skip-validation",
    ]
    if config.min_elev is not None:
        png_export.extend(("--min-elev", _number(config.min_elev)))
    if config.max_elev is not None:
        png_export.extend(("--max-elev", _number(config.max_elev)))
    if config.force_png:
        png_export.append("--force")

    manifest = [
        python,
        str(TOOLS / "write_cs2_bundle_manifest.py"),
        "--center-lon", _number(config.center_lon),
        "--center-lat", _number(config.center_lat),
        "--city", config.city,
        "--country", config.country,
        "--country-code", config.country_code,
        "--bundle-id", config.bundle_id,
        "--bundle-root", bundle_root,
        "--worldmap-size-km", _number(config.worldmap_size_km),
        "--heightmap-size-km", _number(config.heightmap_size_km),
        "--pixels", _number(config.pixels),
        "--tiles", _number(config.tiles),
        "--tile-overlap-px", _number(config.tile_overlap_px),
        f"--world-bbox={config.bbox}",
        f"--heightmap-bbox={config.heightmap_bbox}",
        "--heightmap-normalization", config.heightmap_normalization,
        "--cs2-base-level", _number(config.cs2_base_level),
        "--below-sea-reserve-meters", _number(config.below_sea_reserve_meters),
        "--cs2-elevation-scale", _number(config.cs2_elevation_scale),
        "--cs2-vertical-scale", _number(config.cs2_vertical_scale),
        "--valid-min-elev", _number(config.valid_min_elev),
        "--valid-max-elev", _number(config.valid_max_elev),
        "--write-timeline-config",
        "--check-existing",
    ]
    if config.recommended_cs2_water_level is not None:
        manifest.extend((
            "--recommended-cs2-water-level",
            _number(config.recommended_cs2_water_level),
        ))

    png_validation = [
        python,
        str(TOOLS / "validate_png_contract.py"),
        "--roots", str(png_dir),
        "--center-lon", _number(config.center_lon),
        "--center-lat", _number(config.center_lat),
        "--worldmap-size-km", _number(config.worldmap_size_km),
        "--heightmap-size-km", _number(config.heightmap_size_km),
        "--pixels", _number(config.pixels),
    ]

    bundle_validation = [
        python,
        str(TOOLS / "validate_cs2_bundle.py"),
        "--bundle", str(bundle_dir),
        "--bundle-index", str(bundle_index),
        "--require-active",
    ]

    steps = [
        PipelineStep("extract", "Extraction GeoJSON complète", tuple(extraction)),
        PipelineStep("png", "Export worldmap et heightmap", tuple(png_export)),
        PipelineStep("manifest", "Manifeste et configuration Timeline", tuple(manifest)),
        PipelineStep("validate-png", "Validation du contrat PNG", tuple(png_validation)),
        PipelineStep("validate-bundle", "Validation exhaustive du bundle", tuple(bundle_validation)),
    ]

    if not config.no_sync:
        sync = [
            python,
            str(TOOLS / "sync_citytimeline_bundle.py"),
            "--source-root", str((ROOT / config.bundle_root).resolve()),
            "--bundle-id", config.bundle_id,
        ]
        if config.target_root is not None:
            sync.extend(("--target-root", str(config.target_root)))
        if config.allow_running_game:
            sync.append("--allow-running-game")
        steps.append(
            PipelineStep("sync", "Synchronisation atomique CityTimelineMod", tuple(sync))
        )

    return steps


def _terrain_environment(
    config: BundleBuildConfig,
    environ: Mapping[str, str],
) -> dict[str, str]:
    result = dict(environ)
    canonical = "MAPTILER_API_KEY" if config.provider == "maptiler" else "MAPBOX_TOKEN"
    candidates = [
        config.terrain_token_env,
        canonical,
        "PUBLIC_MAPBOX_TOKEN" if config.provider == "mapbox" else None,
    ]
    source_name = next((name for name in candidates if name and result.get(name)), None)
    if source_name is None and config.prompt_terrain_token:
        token = getpass.getpass(f"{canonical} (session courante uniquement) : ").strip()
        if token:
            result[canonical] = token
            source_name = canonical
    if source_name is None:
        requested = config.terrain_token_env or canonical
        raise PipelineError(
            f"Jeton {config.provider} absent. Définissez {requested} dans cette session "
            "ou utilisez --prompt-terrain-token."
        )
    if source_name != canonical:
        result[canonical] = result[source_name]
    return result


def format_command(command: Sequence[str]) -> str:
    """Affichage Windows fidèle, sans exécuter la commande dans un shell."""

    return subprocess.list2cmdline(list(command))


Runner = Callable[..., subprocess.CompletedProcess]


def run_pipeline(
    config: BundleBuildConfig,
    *,
    runner: Runner = subprocess.run,
    environ: Mapping[str, str] | None = None,
) -> list[PipelineStep]:
    steps = build_pipeline(config)
    if config.dry_run:
        for index, step in enumerate(steps, start=1):
            print(f"[{index}/{len(steps)}] {step.label}")
            print(f"  {format_command(step.command)}")
        return steps

    child_environment = _terrain_environment(config, environ or os.environ)
    print(f"Bundle complet : {config.bundle_id}")
    print(f"Étapes         : {len(steps)}")
    print(
        "Publication    : "
        + ("désactivée (--no-sync)" if config.no_sync else "CityTimelineMod après validation")
    )

    for index, step in enumerate(steps, start=1):
        print("")
        print(f"[{index}/{len(steps)}] {step.label}")
        print(f"  {format_command(step.command)}")
        try:
            runner(
                list(step.command),
                cwd=ROOT,
                env=child_environment,
                check=True,
                shell=False,
            )
        except subprocess.CalledProcessError as exc:
            raise PipelineError(
                f"Étape '{step.label}' interrompue (code {exc.returncode}). "
                "Aucune étape suivante n'a été lancée."
            ) from exc

    print("")
    print(f"[OK] Bundle complet validé : {config.bundle_id}")
    if not config.no_sync:
        print("[OK] Bundle publié atomiquement vers CityTimelineMod.")
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extraction OSM, PNG, manifeste, validations et synchronisation "
            "CityTimelineMod en une commande."
        )
    )
    identity = parser.add_argument_group("Identité et emprises")
    identity.add_argument("--city", required=True)
    identity.add_argument("--country", required=True)
    identity.add_argument("--country-code", required=True)
    identity.add_argument("--bundle-id", required=True)
    identity.add_argument("--bbox", required=True, help="sud,ouest,nord,est (worldmap)")
    identity.add_argument("--heightmap-bbox", required=True, help="sud,ouest,nord,est")
    identity.add_argument("--center-lon", type=float, required=True)
    identity.add_argument("--center-lat", type=float, required=True)

    terrain = parser.add_argument_group("PNG et élévation")
    terrain.add_argument("--worldmap-size-km", type=float, default=57.344)
    terrain.add_argument("--heightmap-size-km", type=float, default=14.336)
    terrain.add_argument("--pixels", type=int, default=4096)
    terrain.add_argument("--provider", choices=("maptiler", "mapbox"), default="maptiler")
    terrain.add_argument("--zoom", type=int, default=14)
    terrain.add_argument("--tiles", type=int, default=4)
    terrain.add_argument("--tile-overlap-px", type=int, default=128)
    terrain.add_argument(
        "--heightmap-normalization",
        choices=("local-minmax", "nonta-manual", "absolute", "absolute-0-scale"),
        default="nonta-manual",
    )
    terrain.add_argument("--cs2-base-level", type=float, default=1.0)
    terrain.add_argument("--below-sea-reserve-meters", type=float, default=511.7)
    terrain.add_argument("--cs2-elevation-scale", type=float, default=4096.0)
    terrain.add_argument("--cs2-vertical-scale", type=float, default=1.0)
    terrain.add_argument("--valid-min-elev", type=float, default=-200.0)
    terrain.add_argument("--valid-max-elev", type=float, default=5000.0)
    terrain.add_argument("--min-elev", type=float, default=None)
    terrain.add_argument("--max-elev", type=float, default=None)
    terrain.add_argument("--recommended-cs2-water-level", type=float, default=None)
    terrain.add_argument("--force-png", action="store_true")
    terrain.add_argument(
        "--terrain-token-env",
        "--maptiler-api-key-env",
        dest="terrain_token_env",
        default=None,
        help=(
            "Variable contenant le jeton terrain. Défaut : MAPTILER_API_KEY "
            "(ou MAPBOX_TOKEN avec --provider mapbox)."
        ),
    )
    terrain.add_argument(
        "--prompt-terrain-token",
        action="store_true",
        help="Demande le jeton masqué s'il est absent de l'environnement.",
    )

    extraction = parser.add_argument_group("Cache Overpass")
    extraction.add_argument("--overpass-cache-dir", type=Path, default=None)
    extraction.add_argument("--no-overpass-cache", action="store_true")
    extraction.add_argument("--refresh-overpass-cache", action="store_true")

    publication = parser.add_argument_group("Sortie et publication")
    publication.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    publication.add_argument("--target-root", type=Path, default=None)
    publication.add_argument("--no-sync", action="store_true")
    publication.add_argument(
        "--allow-running-game",
        action="store_true",
        help=(
            "Autorise explicitement la synchronisation si Cities2.exe tourne. "
            "Par défaut, la publication est refusée jeu ouvert."
        ),
    )
    publication.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche toutes les commandes sans modifier de fichier ni accéder au réseau.",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> BundleBuildConfig:
    return BundleBuildConfig(**vars(args))


def _normalize_negative_bbox_arguments(argv: Sequence[str]) -> list[str]:
    """Accepte aussi ``--bbox "-35,..."`` avec argparse sous Windows."""

    result: list[str] = []
    index = 0
    bbox_options = {"--bbox", "--heightmap-bbox"}
    while index < len(argv):
        value = argv[index]
        if value in bbox_options and index + 1 < len(argv):
            following = argv[index + 1]
            if following.startswith("-") and "," in following:
                result.append(f"{value}={following}")
                index += 2
                continue
        result.append(value)
        index += 1
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    return build_parser().parse_args(_normalize_negative_bbox_arguments(raw))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = config_from_args(parse_args(argv))
        run_pipeline(config)
    except PipelineError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
