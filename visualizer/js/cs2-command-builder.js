(function (App) {
  "use strict";

  var HEIGHTMAP_PIXELS = 4096;
  var CS2_HEIGHTMAP_NORMALIZATION = "nonta-manual";
  var CS2_DEFAULT_SEA_LEVEL = 511.7;
  var CS2_BASE_LEVEL = 1.000;
  var CS2_ELEVATION_SCALE = 4096;
  var CS2_VERTICAL_SCALE = 1.0;
  var CS2_BELOW_SEA_RESERVE_METERS = CS2_DEFAULT_SEA_LEVEL / CS2_VERTICAL_SCALE;
  var CS2_VALID_MIN_ELEV = -200;
  var CS2_VALID_MAX_ELEV = 5000;

  function quoteArg(value) {
    return '"' + String(value).replace(/"/g, "'") + '"';
  }

  function roundNumber(value, digits) {
    var factor = Math.pow(10, digits);
    return Math.round(Number(value) * factor) / factor;
  }

  function getBundleDirPs(bundleMeta) {
    return bundleMeta.dir;
  }

  function buildCommand(cityName, bboxText, bundleMeta) {
    var pythonExe = "python";
    var scriptPath = ".\\src\\extract_zoning.py";
    return [
      "& " + quoteArg(pythonExe),
      quoteArg(scriptPath),
      "--city", quoteArg(cityName),
      "--country", quoteArg(bundleMeta.country),
      "--country-code", quoteArg(bundleMeta.countryCode),
      "--bbox", quoteArg(bboxText),
      "--bundle-output",
      "--bundle-id", quoteArg(bundleMeta.id),
      "--split-layers"
    ].join(" ");
  }

  function buildFullBundleCommand(state, bundleMeta) {
    var pythonExe = "python";

    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldMapKm = roundNumber(state.worldMapSizeKm, 3);
    var heightmapKm = roundNumber(state.heightmapSizeKm, 3);
    var bundle = getBundleDirPs(bundleMeta);
    var geoDir = "$bundle\\geojson_pack";
    var pngDir = "$bundle\\png";

    return [
      "if (-not (Test-Path '.\\src\\extract_zoning.py')) { throw 'Lance ce script depuis la racine du depot cs2-realmap-generator.' }",
      "",
      "if (-not $env:MAPTILER_API_KEY) {",
      "  Write-Host " + quoteArg("MAPTILER_API_KEY absent pour cette session PowerShell.") + " -ForegroundColor Yellow",
      "  Write-Host " + quoteArg("Colle ta clé MapTiler puis appuie sur Entrée.") + " -ForegroundColor Cyan",
      "",
      "  $secureKey = Read-Host " + quoteArg("MAPTILER_API_KEY") + " -AsSecureString",
      "  $plainKey = [System.Net.NetworkCredential]::new(" + quoteArg("") + ", $secureKey).Password",
      "",
      "  if ([string]::IsNullOrWhiteSpace($plainKey)) {",
      "    throw " + quoteArg("MAPTILER_API_KEY vide. Génération annulée."),
      "  }",
      "",
      "  $env:MAPTILER_API_KEY = $plainKey",
      "",
      "  Remove-Variable plainKey -ErrorAction SilentlyContinue",
      "",
      "  Write-Host " + quoteArg("MAPTILER_API_KEY chargée pour cette session PowerShell.") + " -ForegroundColor Green",
      "}",
      "",
      "$lon = " + quoteArg(centerLon),
      "$lat = " + quoteArg(centerLat),
      "$bundleId = " + quoteArg(bundleMeta.id),
      "$city = " + quoteArg(bundleMeta.city),
      "$country = " + quoteArg(bundleMeta.country),
      "$countryCode = " + quoteArg(bundleMeta.countryCode),
      "$bundle = " + quoteArg(bundle),
      "$geoDir = " + quoteArg(geoDir),
      "$pngDir = " + quoteArg(pngDir),
      "",
      "New-Item -ItemType Directory -Force $geoDir | Out-Null",
      "New-Item -ItemType Directory -Force $pngDir | Out-Null",
      "",
      "& " + quoteArg(pythonExe) + " " + quoteArg(".\\src\\extract_zoning.py") + " `",
      "  --city $city `",
      "  --country $country `",
      "  --country-code $countryCode `",
      "  --bbox " + quoteArg(state.heightmapBBoxText) + " `",
      "  --bundle-output `",
      "  --bundle-id $bundleId `",
      "  --split-layers",
      "",
      "& " + quoteArg(pythonExe) + " " + quoteArg(".\\tools\\export_cs2_pngs.py") + " `",
      "  --center-lon $lon `",
      "  --center-lat $lat `",
      "  --worldmap-size-km " + quoteArg(worldMapKm) + " `",
      "  --heightmap-size-km " + quoteArg(heightmapKm) + " `",
      "  --pixels " + quoteArg(HEIGHTMAP_PIXELS) + " `",
      "  --bundle-output `",
      "  --bundle-id $bundleId `",
      "  --city $city `",
      "  --country $country `",
      "  --country-code $countryCode `",
      "  --provider " + quoteArg("maptiler") + " `",
      "  --zoom " + quoteArg(14) + " `",
      "  --heightmap-normalization " + quoteArg(CS2_HEIGHTMAP_NORMALIZATION) + " `",
      "  --cs2-base-level " + quoteArg(CS2_BASE_LEVEL) + " `",
      "  --below-sea-reserve-meters " + quoteArg(CS2_BELOW_SEA_RESERVE_METERS) + " `",
      "  --cs2-elevation-scale " + quoteArg(CS2_ELEVATION_SCALE) + " `",
      "  --cs2-vertical-scale " + quoteArg(CS2_VERTICAL_SCALE) + " `",
      "  --valid-min-elev " + quoteArg(CS2_VALID_MIN_ELEV) + " `",
      "  --valid-max-elev " + quoteArg(CS2_VALID_MAX_ELEV),
      "",
      "& " + quoteArg(pythonExe) + " " + quoteArg(".\\tools\\write_cs2_bundle_manifest.py") + " `",
      "  --center-lon $lon `",
      "  --center-lat $lat `",
      "  --city $city `",
      "  --country $country `",
      "  --country-code $countryCode `",
      "  --bundle-id $bundleId `",
      "  --worldmap-size-km " + quoteArg(worldMapKm) + " `",
      "  --heightmap-size-km " + quoteArg(heightmapKm) + " `",
      "  --world-bbox " + quoteArg(state.worldMapBBoxText) + " `",
      "  --heightmap-bbox " + quoteArg(state.heightmapBBoxText) + " `",
      "  --cs2-base-level " + quoteArg(CS2_BASE_LEVEL) + " `",
      "  --below-sea-reserve-meters " + quoteArg(CS2_BELOW_SEA_RESERVE_METERS) + " `",
      "  --cs2-elevation-scale " + quoteArg(CS2_ELEVATION_SCALE) + " `",
      "  --cs2-vertical-scale " + quoteArg(CS2_VERTICAL_SCALE) + " `",
      "  --write-timeline-config `",
      "  --check-existing",
      "",
      "& " + quoteArg(pythonExe) + " " + quoteArg(".\\tools\\validate_png_contract.py") + " `",
      "  --roots $pngDir `",
      "  --center-lon $lon `",
      "  --center-lat $lat `",
      "  --worldmap-size-km " + quoteArg(worldMapKm) + " `",
      "  --heightmap-size-km " + quoteArg(heightmapKm) + " `",
      "  --pixels " + quoteArg(HEIGHTMAP_PIXELS),
      "",
      "$timelineBundles = " + quoteArg("$env:USERPROFILE\\AppData\\LocalLow\\Colossal Order\\Cities Skylines II\\Mods\\CityTimelineMod\\data\\exports\\bundles"),
      "",
      "New-Item -ItemType Directory -Force $timelineBundles | Out-Null",
      "Copy-Item " + quoteArg(".\\exports\\bundles\\bundle_index.json") + " " + quoteArg("$timelineBundles\\bundle_index.json") + " -Force",
      "Copy-Item $bundle " + quoteArg("$timelineBundles\\$bundleId") + " -Recurse -Force",
      "Write-Host " + quoteArg("Bundle synchronisé vers TimelineMod :") + " $bundleId -ForegroundColor Green",
      "",
      "tree $bundle /F"
    ].join("\n");
  }

  App.CS2CommandBuilder = {
    defaultRecommendedWaterLevel: CS2_DEFAULT_SEA_LEVEL,
    formatNumber: function (value, digits) {
      return Number(value).toFixed(digits);
    },
    roundNumber: roundNumber,
    buildCommand: buildCommand,
    buildFullBundleCommand: buildFullBundleCommand
  };
})(window.CS2Zoning = window.CS2Zoning || {});
