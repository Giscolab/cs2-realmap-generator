from __future__ import annotations

"""Publication sûre et reprenable du bundle actif vers CityTimelineMod.

Ordre garanti : validation source -> copie en staging -> validation staging ->
bascule du dossier complet -> écriture atomique de bundle_index.json EN DERNIER.
Ainsi l'index du mod ne peut pas désigner un bundle partiellement copié.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from validate_cs2_bundle import BundleValidationError, validate_bundle_directory


ROOT = Path(__file__).resolve().parents[1]


def _load_index(path: Path) -> tuple[dict, bytes]:
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except FileNotFoundError as exc:
        raise BundleValidationError(f"bundle_index.json source manquant : {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleValidationError(f"bundle_index.json source illisible : {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise BundleValidationError("bundle_index.json source doit être un objet")
    return data, raw


def _default_target_root() -> Path:
    profile = os.environ.get("USERPROFILE")
    if not profile:
        raise BundleValidationError(
            "USERPROFILE absent : fournissez --target-root explicitement"
        )
    return (
        Path(profile)
        / "AppData"
        / "LocalLow"
        / "Colossal Order"
        / "Cities Skylines II"
        / "Mods"
        / "CityTimelineMod"
        / "data"
        / "exports"
        / "bundles"
    )


def _ensure_child(root: Path, path: Path, label: str) -> None:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    if path_resolved == root_resolved or root_resolved not in path_resolved.parents:
        raise BundleValidationError(f"{label} sort de la racine autorisée : {path_resolved}")


def _mirror_tree(source: Path, destination: Path) -> None:
    """Miroir déterministe ; une reprise corrige un staging interrompu."""
    destination.mkdir(parents=True, exist_ok=True)

    for source_path in source.rglob("*"):
        if source_path.is_symlink():
            raise BundleValidationError(f"Lien symbolique interdit dans le bundle : {source_path}")
        relative = source_path.relative_to(source)
        destination_path = destination / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    # Supprime uniquement les résidus du staging dédié, jamais le bundle actif.
    destination_paths = sorted(
        destination.rglob("*"),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for destination_path in destination_paths:
        relative = destination_path.relative_to(destination)
        if (source / relative).exists():
            continue
        if destination_path.is_dir() and not destination_path.is_symlink():
            destination_path.rmdir()
        else:
            destination_path.unlink()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inventory(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, _file_digest(path))
        for path in root.rglob("*")
        if path.is_file()
    }


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".publishing")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _is_game_running() -> bool:
    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq Cities2.exe", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        # Un échec du contrôle ne doit pas être interprété comme un jeu arrêté.
        return True
    return '"cities2.exe"' in completed.stdout.casefold()


def _canonical_index_entry(bundle_dir: Path, preferred: dict | None) -> dict:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    bundle = manifest["bundle"]
    bundle_id = bundle["id"]
    country_code = str(bundle.get("countryCode") or "")
    water = manifest.get("water") or {}
    recommended_water = water.get(
        "recommendedCs2WaterLevel",
        bundle.get("recommendedCs2WaterLevel"),
    )
    entry = dict(preferred or {})
    entry.update({
        "id": bundle_id,
        "displayName": entry.get("displayName") or ", ".join(
            part for part in (bundle.get("city") or "", country_code.upper()) if part
        ) or bundle_id,
        "city": bundle.get("city") or "",
        "country": bundle.get("country") or "",
        "countryCode": country_code,
        "centerLon": manifest["center"]["lon"],
        "centerLat": manifest["center"]["lat"],
        "relativePath": bundle_id,
        "manifestPath": f"{bundle_id}/manifest.json",
        "bundlePath": bundle_id,
        "recommendedWaterLevel": recommended_water,
        "recommendedCs2WaterLevel": recommended_water,
        "worldmapSizeKm": manifest["worldMap"]["sizeKm"],
        "heightmapSizeKm": manifest["heightmap"]["sizeKm"],
    })
    return entry


def _coherent_target_index(
    target_root: Path,
    source_index: dict,
    previous_index: dict | None,
    active_id: str,
) -> dict:
    source_entries = {
        str(entry.get("id")): entry
        for entry in source_index.get("bundles", [])
        if isinstance(entry, dict) and entry.get("id")
    }
    previous_entries = {
        str(entry.get("id")): entry
        for entry in (previous_index or {}).get("bundles", [])
        if isinstance(entry, dict) and entry.get("id")
    }

    entries: list[dict] = []
    for bundle_dir in sorted(target_root.iterdir(), key=lambda path: path.name):
        if not bundle_dir.is_dir() or bundle_dir.name.startswith("."):
            continue
        if not (bundle_dir / "manifest.json").is_file():
            continue
        try:
            report = validate_bundle_directory(bundle_dir)
        except BundleValidationError:
            # Un ancien dossier incomplet reste hors catalogue au lieu de rendre
            # bundle_index.json mensonger.
            continue
        bundle_id = report["bundleId"]
        preferred = source_entries.get(bundle_id) or previous_entries.get(bundle_id)
        entries.append(_canonical_index_entry(bundle_dir, preferred))

    if active_id not in {entry["id"] for entry in entries}:
        raise BundleValidationError(
            f"Le bundle actif {active_id!r} n'est pas validable dans la destination"
        )

    return {
        "schemaVersion": source_index.get("schemaVersion", 1),
        "version": source_index.get("version", 1),
        "activeBundleId": active_id,
        "bundles": sorted(
            entries,
            key=lambda item: (
                str(item.get("country", "")),
                str(item.get("city", "")),
                str(item.get("id", "")),
            ),
        ),
    }


def sync_active_bundle(
    source_root: Path,
    target_root: Path,
    *,
    bundle_id: str | None = None,
    allow_running_game: bool = False,
    game_running: bool | None = None,
) -> dict:
    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()
    if source_root == target_root:
        raise BundleValidationError("Les racines source et destination doivent être distinctes")
    running = _is_game_running() if game_running is None else game_running
    if running and not allow_running_game:
        raise BundleValidationError(
            "Cities2.exe est en cours d'exécution. Fermez le jeu avant la publication "
            "(ou utilisez explicitement --allow-running-game à vos risques)."
        )

    source_index_path = source_root / "bundle_index.json"
    source_index, _ = _load_index(source_index_path)
    active_id = str(source_index.get("activeBundleId") or "").strip()
    selected_id = str(bundle_id or active_id).strip()
    if not selected_id:
        raise BundleValidationError("activeBundleId absent du bundle_index.json source")
    if selected_id != active_id:
        raise BundleValidationError(
            f"Le bundle demandé {selected_id!r} n'est pas le bundle actif source {active_id!r}. "
            "Régénérez le manifeste/index avant la synchronisation."
        )
    if Path(selected_id).name != selected_id or selected_id in (".", ".."):
        raise BundleValidationError(f"Identifiant de bundle non sûr : {selected_id!r}")

    source_bundle = source_root / selected_id
    _ensure_child(source_root, source_bundle, "Bundle source")
    validate_bundle_directory(
        source_bundle,
        bundle_index_path=source_index_path,
        require_active=True,
    )

    target_root.mkdir(parents=True, exist_ok=True)
    staging_root = target_root / f".{selected_id}.staging"
    staging_bundle = staging_root / selected_id
    backup_root = target_root / f".{selected_id}.backup"
    backup_bundle = backup_root / selected_id
    target_bundle = target_root / selected_id
    target_index_path = target_root / "bundle_index.json"
    for label, path in (
        ("Staging", staging_root),
        ("Sauvegarde", backup_root),
        ("Bundle cible", target_bundle),
    ):
        _ensure_child(target_root, path, label)

    # Répare d'abord une interruption survenue entre sauvegarde et bascule.
    if backup_bundle.exists() and not target_bundle.exists():
        backup_bundle.replace(target_bundle)

    _mirror_tree(source_bundle, staging_bundle)
    if _inventory(source_bundle) != _inventory(staging_bundle):
        raise BundleValidationError("La copie staging ne correspond pas bit à bit au bundle source")
    validate_bundle_directory(staging_bundle)

    previous_index = target_index_path.read_bytes() if target_index_path.is_file() else None
    try:
        previous_index_data = json.loads(previous_index.decode("utf-8")) if previous_index else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        previous_index_data = None
    had_previous_bundle = target_bundle.exists()
    swapped = False

    try:
        if backup_root.exists():
            # Ce répertoire est un artefact privé vérifié sous target_root.
            shutil.rmtree(backup_root)
        backup_root.mkdir(parents=True)

        if had_previous_bundle:
            target_bundle.replace(backup_bundle)
        staging_bundle.replace(target_bundle)
        swapped = True

        # Point de publication : activeBundleId est celui du générateur, mais
        # seules les entrées réellement présentes et validées sont publiées.
        # L'index arrive uniquement après la bascule réussie du bundle complet.
        target_index = _coherent_target_index(
            target_root,
            source_index,
            previous_index_data,
            selected_id,
        )
        _atomic_write_bytes(target_index_path, _json_bytes(target_index))
        deployed_report = validate_bundle_directory(
            target_bundle,
            bundle_index_path=target_index_path,
            require_active=True,
        )
    except Exception:
        if previous_index is None:
            if target_index_path.exists():
                target_index_path.unlink()
        else:
            _atomic_write_bytes(target_index_path, previous_index)

        if swapped and target_bundle.exists():
            staging_root.mkdir(parents=True, exist_ok=True)
            target_bundle.replace(staging_bundle)
        if had_previous_bundle and backup_bundle.exists():
            backup_bundle.replace(target_bundle)
        raise
    else:
        if backup_root.exists():
            shutil.rmtree(backup_root)
        if staging_root.exists():
            shutil.rmtree(staging_root)

    return {
        "bundleId": selected_id,
        "source": str(source_bundle),
        "target": str(target_bundle),
        "fileCount": len(_inventory(target_bundle)),
        "geojsonFileCount": deployed_report["geojsonFileCount"],
        "layerCount": deployed_report["layerCount"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise atomiquement le bundle actif vers CityTimelineMod."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / "exports" / "bundles",
    )
    parser.add_argument("--target-root", type=Path, default=None)
    parser.add_argument("--bundle-id", default=None)
    parser.add_argument(
        "--allow-running-game",
        action="store_true",
        help="Autorise explicitement la publication pendant que Cities2.exe tourne.",
    )
    args = parser.parse_args()

    try:
        target_root = args.target_root or _default_target_root()
        report = sync_active_bundle(
            args.source_root,
            target_root,
            bundle_id=args.bundle_id,
            allow_running_game=args.allow_running_game,
        )
    except (BundleValidationError, OSError) as exc:
        print(f"[ERREUR] Synchronisation annulée sans publier d'index incomplet : {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] Bundle actif synchronisé intégralement : "
        f"{report['bundleId']} — {report['fileCount']} fichiers, "
        f"{report['geojsonFileCount']} GeoJSON."
    )
    print(f"Destination : {report['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
