import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from build_complete_bundle import (  # noqa: E402
    BundleBuildConfig,
    PipelineError,
    build_pipeline,
    config_from_args,
    parse_args,
    run_pipeline,
)


def _config(**changes) -> BundleBuildConfig:
    values = {
        "city": "Canberra",
        "country": "Australia",
        "country_code": "au",
        "bundle_id": "canberra_au_-35.281000_149.128000",
        "bbox": "-35.539433,148.812836,-35.022567,149.443164",
        "heightmap_bbox": "-35.345608,149.049209,-35.216392,149.206791",
        "center_lon": 149.128,
        "center_lat": -35.281,
    }
    values.update(changes)
    return BundleBuildConfig(**values)


def _value_after(command: tuple[str, ...], option: str) -> str:
    return command[command.index(option) + 1]


def test_complete_pipeline_has_the_six_ordered_steps_and_same_python() -> None:
    steps = build_pipeline(_config(target_root=Path("D:/Timeline/bundles")))

    assert [step.key for step in steps] == [
        "extract",
        "png",
        "manifest",
        "validate-png",
        "validate-bundle",
        "sync",
    ]
    assert all(step.command[0] == sys.executable for step in steps)
    assert "--split-layers" in steps[0].command
    assert "--skip-validation" in steps[1].command
    assert "--write-timeline-config" in steps[2].command
    assert "--check-existing" in steps[2].command
    assert "--require-active" in steps[4].command
    assert _value_after(steps[5].command, "--target-root") == "D:\\Timeline\\bundles"
    assert "--allow-running-game" not in steps[5].command


def test_all_geographic_terrain_and_elevation_values_are_forwarded() -> None:
    config = _config(
        worldmap_size_km=60.0,
        heightmap_size_km=15.0,
        pixels=8192,
        provider="mapbox",
        zoom=13,
        tiles=8,
        tile_overlap_px=96,
        heightmap_normalization="absolute",
        cs2_base_level=2.0,
        below_sea_reserve_meters=500.0,
        cs2_elevation_scale=8192.0,
        cs2_vertical_scale=2.0,
        valid_min_elev=-500.0,
        valid_max_elev=6000.0,
        min_elev=-20.0,
        max_elev=1400.0,
        recommended_cs2_water_level=512.0,
        force_png=True,
    )
    extraction, png, manifest, *_ = build_pipeline(config)

    assert f"--bbox={config.bbox}" in extraction.command
    assert _value_after(png.command, "--provider") == "mapbox"
    assert _value_after(png.command, "--pixels") == "8192"
    assert _value_after(png.command, "--tiles") == "8"
    assert _value_after(png.command, "--min-elev") == "-20.0"
    assert _value_after(png.command, "--max-elev") == "1400.0"
    assert "--force" in png.command
    assert f"--world-bbox={config.bbox}" in manifest.command
    assert f"--heightmap-bbox={config.heightmap_bbox}" in manifest.command
    assert _value_after(manifest.command, "--recommended-cs2-water-level") == "512.0"


def test_overpass_cache_modes_and_no_sync_are_explicit() -> None:
    cached = build_pipeline(
        _config(
            overpass_cache_dir=Path("exports/.overpass-cache/canberra"),
            refresh_overpass_cache=True,
            no_sync=True,
        )
    )
    assert len(cached) == 5
    assert _value_after(cached[0].command, "--overpass-cache-dir").endswith("canberra")
    assert "--refresh-overpass-cache" in cached[0].command

    uncached = build_pipeline(_config(no_overpass_cache=True, no_sync=True))
    assert "--no-overpass-cache" in uncached[0].command


def test_pipeline_calls_subprocess_without_shell_and_never_puts_token_in_command() -> None:
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    secret = "test-secret-not-for-command-line"
    steps = run_pipeline(
        _config(no_sync=True, terrain_token_env="PRIVATE_MAP_KEY"),
        runner=fake_runner,
        environ={"PRIVATE_MAP_KEY": secret},
    )

    assert len(calls) == len(steps) == 5
    for command, kwargs in calls:
        assert command[0] == sys.executable
        assert kwargs["cwd"] == ROOT
        assert kwargs["check"] is True
        assert kwargs["shell"] is False
        assert kwargs["env"]["MAPTILER_API_KEY"] == secret
        assert secret not in command


def test_missing_maptiler_key_stops_before_any_subprocess() -> None:
    called = False

    def fake_runner(command, **kwargs):
        nonlocal called
        called = True

    with pytest.raises(PipelineError, match="MAPTILER_API_KEY"):
        run_pipeline(_config(no_sync=True), runner=fake_runner, environ={})
    assert called is False


def test_dry_run_needs_no_key_and_runs_nothing() -> None:
    called = False

    def fake_runner(command, **kwargs):
        nonlocal called
        called = True

    steps = run_pipeline(
        _config(no_sync=True, dry_run=True),
        runner=fake_runner,
        environ={},
    )
    assert len(steps) == 5
    assert called is False


def test_negative_bbox_values_are_accepted_as_separate_windows_arguments() -> None:
    args = parse_args([
        "--city", "Canberra",
        "--country", "Australia",
        "--country-code", "au",
        "--bundle-id", "canberra",
        "--bbox", "-35.5,148.8,-35.0,149.4",
        "--heightmap-bbox", "-35.3,149.0,-35.2,149.2",
        "--center-lon", "149.128",
        "--center-lat", "-35.281",
        "--no-sync",
    ])
    config = config_from_args(args)
    assert config.bbox.startswith("-35.5")
    assert config.heightmap_bbox.startswith("-35.3")
    assert config.no_sync is True


def test_invalid_contract_is_rejected_before_execution() -> None:
    cases = [
        ({"bbox": "-35,149,-36,150"}, "mal ordonnée"),
        ({"center_lon": 12.0}, "centre"),
        ({"valid_min_elev": 100, "valid_max_elev": 100}, "valid-min-elev"),
        ({"bundle_id": "nom/interdit"}, "bundle-id"),
        ({"no_overpass_cache": True, "refresh_overpass_cache": True}, "incompatibles"),
    ]
    for changes, message in cases:
        with pytest.raises(PipelineError, match=message):
            build_pipeline(_config(**changes))
