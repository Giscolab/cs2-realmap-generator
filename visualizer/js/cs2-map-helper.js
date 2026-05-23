(function (App) {
  "use strict";

  var CS2_WORLD_SCALE = 1.0;
  var HEIGHTMAP_PIXELS = 4096;
  var CS2_HEIGHTMAP_RESAMPLING = "bilinear";
  var CS2_HEIGHTMAP_NORMALIZATION = "nonta-manual";
  var CS2_DEFAULT_SEA_LEVEL = 511.7;
  var CS2_BASE_LEVEL = 1.000;
  var CS2_ELEVATION_SCALE = 4096;
  var CS2_VERTICAL_SCALE = 1.0;
  var CS2_BELOW_SEA_RESERVE_METERS = CS2_DEFAULT_SEA_LEVEL / CS2_VERTICAL_SCALE;
  var CS2_VALID_MIN_ELEV = -200;
  var CS2_VALID_MAX_ELEV = 5000;

  var DEFAULT_BUNDLE_ID = "irvine_ca_us_33.653495_-117.723999";
  var DEFAULT_BUNDLE_CITY = "Irvine";
  var DEFAULT_BUNDLE_COUNTRY = "United States";
  var DEFAULT_BUNDLE_COUNTRY_CODE = "us";
  var DEFAULT_RECOMMENDED_CS2_WATER_LEVEL = CS2_DEFAULT_SEA_LEVEL;

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(element, value) {
    if (element) {
      element.textContent = value;
    }
  }

  function formatNumber(value, digits) {
    return Number(value).toFixed(digits);
  }

  function getCityName(input) {
    var value = input && input.value ? String(input.value).trim() : "";
    return value;
  }

  function quoteArg(value) {
    return '"' + String(value).replace(/"/g, "'") + '"';
  }

  function stripAccents(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function slugifyBundlePart(value, fallback) {
    var slug = stripAccents(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");

    return slug || fallback;
  }

  function sanitizeBundleId(value) {
    var bundleId = stripAccents(value)
      .toLowerCase()
      .replace(/[^a-z0-9_.-]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");

    return bundleId || "bundle";
  }

  function getInputValue(input, fallback) {
    var value = input && input.value ? String(input.value).trim() : "";
    return value || fallback;
  }

  function getCountryName(context) {
    return getInputValue(context.countryInput, DEFAULT_BUNDLE_COUNTRY);
  }

  function normalizeCountryLookup(value) {
    return stripAccents(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  var COUNTRY_CODE_ALIASES = {
    "indonesie": "id",
    "indonesia": "id",
    "israel": "il",
    "tchequie": "cz",
    "czechia": "cz",
    "czech-republic": "cz",
    "republique-tcheque": "cz",
    "etats-unis": "us",
    "united-states": "us",
    "usa": "us",
    "france": "fr",
    "allemagne": "de",
    "germany": "de",
    "italie": "it",
    "italy": "it",
    "espagne": "es",
    "spain": "es",
    "royaume-uni": "gb",
    "united-kingdom": "gb",
    "uk": "gb",
    "japon": "jp",
    "japan": "jp",
    "chine": "cn",
    "china": "cn",
    "bresil": "br",
    "brazil": "br",
    "mexique": "mx",
    "mexico": "mx",
    "australie": "au",
    "australia": "au",
    "canada": "ca",
    "burkina-faso": "bf"
  };

  function normalizeCountryKey(value) {
    return stripAccents(value)
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function resolveCountryCode(value, countryName) {
    var rawCode = String(value || "").trim().toLowerCase();

    if (/^[a-z]{2}$/.test(rawCode)) {
      return rawCode;
    }

    var normalizedCode = normalizeCountryKey(value);

    if (COUNTRY_CODE_ALIASES[normalizedCode]) {
      return COUNTRY_CODE_ALIASES[normalizedCode];
    }

    var normalizedCountry = normalizeCountryKey(countryName);

    if (COUNTRY_CODE_ALIASES[normalizedCountry]) {
      return COUNTRY_CODE_ALIASES[normalizedCountry];
    }

    return slugifyBundlePart(value || countryName, DEFAULT_BUNDLE_COUNTRY_CODE).slice(0, 2);
  }

  function getCountryCode(context) {
    var rawCode = getInputValue(context.countryCodeInput, "");
    var country = getCountryName(context);
    return resolveCountryCode(rawCode, country);
  }

  function getRecommendedWaterLevel(context) {
    var raw = getInputValue(context.waterLevelInput, DEFAULT_RECOMMENDED_CS2_WATER_LEVEL);
    var value = Number(raw);

    return Number.isFinite(value) ? value : DEFAULT_RECOMMENDED_CS2_WATER_LEVEL;
  }

  function buildDynamicBundleId(cityName, countryCode, centerLon, centerLat) {
    return [
      slugifyBundlePart(cityName, "city"),
      slugifyBundlePart(countryCode, "xx"),
      formatNumber(centerLat, 6),
      formatNumber(centerLon, 6)
    ].join("_");
  }

  function getLoadedBundleId(context, cityName) {
    var indexPath = context && context.packData ? String(context.packData.indexPath || "") : "";
    var match = indexPath.match(/(?:^|\/)exports\/bundles\/([^\/]+)\/geojson_pack\//);

    if (!match) {
      return "";
    }

    var loadedId = sanitizeBundleId(decodeURIComponent(match[1]));
    var expectedCityPrefix = slugifyBundlePart(cityName, "city") + "_";

    return loadedId.indexOf(expectedCityPrefix) === 0 ? loadedId : "";
  }

  function getBundleMeta(context, state, cityName) {
    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var country = getCountryName(context);
    var countryCode = getCountryCode(context);

    if (context.countryCodeInput && context.countryCodeInput.value !== countryCode) {
      context.countryCodeInput.value = countryCode;
    }

    var dynamicBundleId = sanitizeBundleId(
      buildDynamicBundleId(cityName, countryCode, centerLon, centerLat)
    );

    var loadedBundleId = "";
    var indexPath = context && context.packData ? String(context.packData.indexPath || "") : "";
    var match = indexPath.match(/(?:^|\/)exports\/bundles\/([^\/]+)\/geojson_pack\/reports\/layer_index\.json/i);

    if (match && match[1]) {
      loadedBundleId = sanitizeBundleId(decodeURIComponent(match[1]));
    }

    var isDefaultIrvine =
      slugifyBundlePart(cityName, "city") === slugifyBundlePart(DEFAULT_BUNDLE_CITY, "city") &&
      countryCode === DEFAULT_BUNDLE_COUNTRY_CODE &&
      Math.abs(centerLat - 33.653495) < 0.000001 &&
      Math.abs(centerLon - (-117.723999)) < 0.000001;

    var bundleId = loadedBundleId || (isDefaultIrvine ? DEFAULT_BUNDLE_ID : dynamicBundleId);
    var bundleDir = ".\\exports\\bundles\\" + bundleId;

    return {
      id: bundleId,
      city: cityName,
      country: country,
      countryCode: countryCode,
      recommendedCs2WaterLevel: getRecommendedWaterLevel(context),
      dir: bundleDir,
      pngDir: bundleDir + "\\png",
      geojsonDir: bundleDir + "\\geojson_pack"
    };
  }

  function getBundleDirPs(bundleMeta) {
    return bundleMeta.dir;
  }

  function getBundlePngDirPs(bundleMeta) {
    return bundleMeta.pngDir;
  }

  function getBundleGeojsonDirPs(bundleMeta) {
    return bundleMeta.geojsonDir;
  }

  function syncBundleUi(context, bundleMeta) {
    if (context.bundleIdOutput && document.activeElement !== context.bundleIdOutput) {
      context.bundleIdOutput.value = bundleMeta.id;
    }
  }


  function dispatchTargetBundleUpdate(context, state, bundleMeta) {
    var rawCity = context.cityInput && context.cityInput.value
      ? String(context.cityInput.value).trim()
      : "";

    if (!rawCity || !bundleMeta || !bundleMeta.id) {
      window.dispatchEvent(new CustomEvent("cs2zoning:target-bundle-updated", {
        detail: {
          bundleId: "",
          label: "",
          city: "",
          country: "",
          countryCode: "",
          worldBBox: "",
          heightmapBBox: ""
        }
      }));
      return;
    }

    window.dispatchEvent(new CustomEvent("cs2zoning:target-bundle-updated", {
      detail: {
        bundleId: bundleMeta.id || "",
        label: bundleMeta.city && bundleMeta.country
          ? bundleMeta.city + ", " + bundleMeta.country
          : bundleMeta.id,
        city: bundleMeta.city || "",
        country: bundleMeta.country || "",
        countryCode: bundleMeta.countryCode || "",
        worldBBox: state.worldMapBBoxText || "",
        heightmapBBox: state.heightmapBBoxText || ""
      }
    }));
  }

  function buildCommand(cityName, bboxText, state, bundleMeta) {
    var pythonExe = "C:\\Python314\\python.exe";
    var scriptPath = "C:\\Users\\cadet\\Documents\\GitHub\\cs2-realmap-generator\\src\\extract_zoning.py";
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

  function buildCs2PngPipelineCommand(state, bundleMeta) {
    var pythonExe = "C:\\Python314\\python.exe";
    var scriptPath = "C:\\Users\\cadet\\Documents\\GitHub\\cs2-realmap-generator\\tools\\export_cs2_pngs.py";

    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldMapKm = roundNumber(state.worldMapSizeKm, 3);
    var heightmapKm = roundNumber(state.heightmapSizeKm, 3);

    return [
      "& " + quoteArg(pythonExe),
      quoteArg(scriptPath),
      "--center-lon", quoteArg(centerLon),
      "--center-lat", quoteArg(centerLat),
      "--worldmap-size-km", quoteArg(worldMapKm),
      "--heightmap-size-km", quoteArg(heightmapKm),
      "--pixels", quoteArg(HEIGHTMAP_PIXELS),
      "--bundle-output",
      "--bundle-id", quoteArg(bundleMeta.id),
      "--city", quoteArg(bundleMeta.city),
      "--country", quoteArg(bundleMeta.country),
      "--country-code", quoteArg(bundleMeta.countryCode),
      "--provider", quoteArg("maptiler"),
      "--zoom", quoteArg(14),
      "--heightmap-normalization", quoteArg(CS2_HEIGHTMAP_NORMALIZATION),
      "--cs2-base-level", quoteArg(CS2_BASE_LEVEL),
      "--below-sea-reserve-meters", quoteArg(CS2_BELOW_SEA_RESERVE_METERS),
      "--cs2-elevation-scale", quoteArg(CS2_ELEVATION_SCALE),
      "--cs2-vertical-scale", quoteArg(CS2_VERTICAL_SCALE),
      "--valid-min-elev", quoteArg(CS2_VALID_MIN_ELEV),
      "--valid-max-elev", quoteArg(CS2_VALID_MAX_ELEV)
    ].join(" ");
  }

  function buildCs2PngContract(state, bundleMeta) {
    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldMapKm = roundNumber(state.worldMapSizeKm, 3);
    var heightmapKm = roundNumber(state.heightmapSizeKm, 3);
    var outDir = getBundlePngDirPs(bundleMeta);

    return {
      centerLon: centerLon,
      centerLat: centerLat,
      worldmapSizeKm: worldMapKm,
      heightmapSizeKm: heightmapKm,
      pixels: HEIGHTMAP_PIXELS,
      outDir: outDir,
      provider: "maptiler",
      zoom: 14,
      heightmapNormalization: CS2_HEIGHTMAP_NORMALIZATION,
      cs2BaseLevel: CS2_BASE_LEVEL,
      belowSeaReserveMeters: CS2_BELOW_SEA_RESERVE_METERS,
      cs2ElevationScale: CS2_ELEVATION_SCALE,
      cs2VerticalScale: CS2_VERTICAL_SCALE,
      validMinElev: CS2_VALID_MIN_ELEV,
      validMaxElev: CS2_VALID_MAX_ELEV,
      expectedFiles: {
        worldmapPng: "worldmap_" + centerLon + "_" + centerLat + "_" + worldMapKm + ".png",
        heightmapPng: "heightmap_" + centerLon + "_" + centerLat + "_" + heightmapKm + ".png"
      }
    };
  }

  function roundNumber(value, digits) {
    var factor = Math.pow(10, digits);
    return Math.round(Number(value) * factor) / factor;
  }

  function buildFullBundleCommand(cityName, state, bundleMeta) {
    var pythonExe = "C:\\Python314\\python.exe";
    var repoDir = "C:\\Users\\cadet\\Documents\\GitHub\\cs2-realmap-generator";

    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldMapKm = roundNumber(state.worldMapSizeKm, 3);
    var heightmapKm = roundNumber(state.heightmapSizeKm, 3);
    var bundle = getBundleDirPs(bundleMeta);
    var geoDir = "$bundle\\geojson_pack";
    var pngDir = "$bundle\\png";

    return [
      "cd " + quoteArg(repoDir),
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
  function buildTimelineManifest(cityName, state, command, bundleMeta) {
    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldMapKm = roundNumber(state.worldMapSizeKm, 3);
    var heightmapKm = roundNumber(state.heightmapSizeKm, 3);
    var cs2PngContract = buildCs2PngContract(state, bundleMeta);
    var cs2PngPipelineCommand = buildCs2PngPipelineCommand(state, bundleMeta);
    var worldScale = CS2_WORLD_SCALE;

    var manifest = {
      version: 1,
      source: "cs2-realmap-generator",
      city: cityName,
      bboxOrder: "south,west,north,east",
      center: {
        lat: centerLat,
        lon: centerLon
      },
      worldMap: {
        sizeKm: worldMapKm,
        bbox: state.worldMapBBoxText
      },
      heightmap: {
        sizeKm: heightmapKm,
        bbox: state.heightmapBBoxText,
        pixels: HEIGHTMAP_PIXELS,
        format: "PNG grayscale 16-bit"
      },
      timelineMod: {
        useGeoJsonCenter: false,
        originLon: centerLon,
        originLat: centerLat,
        worldOriginX: 0.0,
        worldOriginZ: 0.0,
        worldScale: roundNumber(worldScale, 8),
        overlayRotationDegrees: 0.0,
        overlayScaleX: 1.0,
        overlayScaleZ: 1.0,
        flipX: false,
        flipZ: false
      },
      expectedFiles: {
        heightmapPng: "heightmap_" + centerLon + "_" + centerLat + "_" + heightmapKm + ".png",
        worldmapPng: "worldmap_" + centerLon + "_" + centerLat + "_" + worldMapKm + ".png",
        roadsGeoJson: "roads_major_clipped.geojson",
        waterLinesGeoJson: "water_lines_clipped.geojson",
        waterAreasGeoJson: "water_areas_clipped.geojson"
      },
      geojsonPack: {
        outDir: getBundleGeojsonDirPs(bundleMeta),
        splitLayers: true,
        bboxSource: "heightmap",
        bbox: state.heightmapBBoxText
      },
      exportBundle: {
        bundleManifest: getBundleDirPs(bundleMeta) + "\\manifest.json",
        pngDir: getBundlePngDirPs(bundleMeta),
        geojsonDir: getBundleGeojsonDirPs(bundleMeta),
        worldmapPng: getBundlePngDirPs(bundleMeta) + "\\worldmap_" + centerLon + "_" + centerLat + "_" + worldMapKm + ".png",
        heightmapPng: getBundlePngDirPs(bundleMeta) + "\\heightmap_" + centerLon + "_" + centerLat + "_" + heightmapKm + ".png",
        geojson: {
          roadsMajor: getBundleGeojsonDirPs(bundleMeta) + "\\geojson\\roads_major_clipped.geojson",
          roadsDriveable: getBundleGeojsonDirPs(bundleMeta) + "\\geojson\\roads_driveable_clipped.geojson",
          waterLines: getBundleGeojsonDirPs(bundleMeta) + "\\geojson\\water_lines_clipped.geojson",
          waterAreas: getBundleGeojsonDirPs(bundleMeta) + "\\geojson\\water_areas_clipped.geojson",
          allFeatures: getBundleGeojsonDirPs(bundleMeta) + "\\geojson\\all_features.geojson",
          layerIndex: getBundleGeojsonDirPs(bundleMeta) + "\\reports\\layer_index.json",
          extractionReport: getBundleGeojsonDirPs(bundleMeta) + "\\reports\\extraction_report.json"
        }
      },
      cs2PngPipeline: {
        contract: cs2PngContract,
        contractFilename: "cs2_png_contract_" + centerLon + "_" + centerLat + ".json"
      },
      commands: {
        extractZoning: command,
        exportCs2Pngs: cs2PngPipelineCommand
      }
    };

    return JSON.stringify(manifest, null, 2);
  }

  function buildCs2PngContractText(state, bundleMeta) {
    return JSON.stringify(buildCs2PngContract(state, bundleMeta), null, 2);
  }

  function ensureCs2PngContractUi(context) {
    if (byId("cs2-helper-png-contract")) {
      return;
    }

    if (!context.timelineManifestOutput || !context.timelineConfigOutput) {
      return;
    }

    var manifestBlock = context.timelineManifestOutput.parentElement;
    var configBlock = context.timelineConfigOutput.parentElement;
    var container = configBlock && configBlock.parentElement;

    if (!manifestBlock || !configBlock || !container) {
      return;
    }

    var section = document.createElement("section");
    section.className = "cs2-helper-generated-section";
    section.style.borderTop = "1px solid rgba(255, 255, 255, 0.12)";
    section.style.marginTop = "12px";
    section.style.paddingTop = "12px";

    var title = document.createElement("h3");
    title.textContent = "Contrat PNG CS2";

    var actions = document.createElement("div");
    actions.className = "cs2-helper-actions";

    var copyButton = document.createElement("button");
    copyButton.id = "copy-cs2-png-contract";
    copyButton.type = "button";
    copyButton.textContent = "Copier";

    var downloadButton = document.createElement("button");
    downloadButton.id = "download-cs2-png-contract";
    downloadButton.type = "button";
    downloadButton.textContent = "Télécharger";

    var output = document.createElement("pre");
    output.id = "cs2-helper-png-contract";
    output.className = "cs2-helper-output";

    actions.appendChild(copyButton);
    actions.appendChild(downloadButton);

    section.appendChild(title);
    section.appendChild(actions);
    section.appendChild(output);

    container.insertBefore(section, configBlock);

    copyButton.addEventListener("click", function () {
      copyText(context.currentCs2PngContract || "", function () {
        flashButton(copyButton, "Copié");
      });
    });

    downloadButton.addEventListener("click", function () {
      downloadCs2PngContract(context);
      flashButton(downloadButton, "Téléchargé");
    });
  }
  function buildExportBundleManifest(state, bundleMeta) {
    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldMapKm = roundNumber(state.worldMapSizeKm, 3);
    var heightmapKm = roundNumber(state.heightmapSizeKm, 3);
    var pngDir = getBundlePngDirPs(bundleMeta);
    var geojsonDir = getBundleGeojsonDirPs(bundleMeta);
    var bundleManifest = getBundleDirPs(bundleMeta) + "\\manifest.json";

    return {
      version: 1,
      source: "cs2-realmap-generator",
      kind: "cs2-export-bundle",
      bundle: {
        id: bundleMeta.id,
        city: bundleMeta.city,
        country: bundleMeta.country,
        countryCode: bundleMeta.countryCode,
        directory: getBundleDirPs(bundleMeta),
        recommendedCs2WaterLevel: bundleMeta.recommendedCs2WaterLevel
      },
      city: bundleMeta.city,
      country: bundleMeta.country,
      center: {
        lon: centerLon,
        lat: centerLat
      },
      bboxOrder: "south,west,north,east",
      worldMap: {
        sizeKm: worldMapKm,
        bbox: state.worldMapBBoxText
      },
      heightmap: {
        sizeKm: heightmapKm,
        bbox: state.heightmapBBoxText,
        pixels: HEIGHTMAP_PIXELS,
        format: "PNG grayscale 16-bit"
      },
      paths: {
        bundleManifest: bundleManifest,
        pngDir: pngDir,
        geojsonDir: geojsonDir,
        worldmapPng: pngDir + "\\worldmap_" + centerLon + "_" + centerLat + "_" + worldMapKm + ".png",
        heightmapPng: pngDir + "\\heightmap_" + centerLon + "_" + centerLat + "_" + heightmapKm + ".png"
      },
      geojson: {
        allFeatures: geojsonDir + "\\geojson\\all_features.geojson",
        zoningPolygons: geojsonDir + "\\geojson\\zoning_polygons.geojson",
        roads: geojsonDir + "\\geojson\\roads.geojson",
        roadsMajor: geojsonDir + "\\geojson\\roads_major_clipped.geojson",
        roadsDriveable: geojsonDir + "\\geojson\\roads_driveable_clipped.geojson",
        paths: geojsonDir + "\\geojson\\paths.geojson",
        waterLines: geojsonDir + "\\geojson\\water_lines_clipped.geojson",
        waterAreas: geojsonDir + "\\geojson\\water_areas_clipped.geojson",
        layerIndex: geojsonDir + "\\reports\\layer_index.json",
        extractionReport: geojsonDir + "\\reports\\extraction_report.json"
      },
      timelineMod: {
        configPath: getBundleDirPs(bundleMeta) + "\\timeline_config.json",
        useGeoJsonCenter: false,
        originLon: centerLon,
        originLat: centerLat,
        worldOriginX: 0,
        worldOriginZ: 0,
        worldScale: CS2_WORLD_SCALE,
        overlayRotationDegrees: 0,
        overlayScaleX: 1,
        overlayScaleZ: 1,
        flipX: false,
        flipZ: false
      },
      expectedFiles: {
        worldmapPng: "worldmap_" + centerLon + "_" + centerLat + "_" + worldMapKm + ".png",
        heightmapPng: "heightmap_" + centerLon + "_" + centerLat + "_" + heightmapKm + ".png",
        roadsMajorGeoJson: "roads_major_clipped.geojson",
        roadsDriveableGeoJson: "roads_driveable_clipped.geojson",
        waterLinesGeoJson: "water_lines_clipped.geojson",
        waterAreasGeoJson: "water_areas_clipped.geojson"
      }
    };
  }

  function buildExportBundleManifestText(state, bundleMeta) {
    return JSON.stringify(buildExportBundleManifest(state, bundleMeta), null, 2);
  }

  function ensureExportBundleUi(context) {
    if (byId("cs2-helper-export-bundle")) {
      return;
    }

    if (!context.timelineConfigOutput) {
      return;
    }

    var configBlock = context.timelineConfigOutput.parentElement;
    var container = configBlock && configBlock.parentElement;

    if (!configBlock || !container) {
      return;
    }

    var section = document.createElement("section");
    section.className = "cs2-helper-generated-section";
    section.style.borderTop = "1px solid rgba(255, 255, 255, 0.12)";
    section.style.marginTop = "12px";
    section.style.paddingTop = "12px";

    var title = document.createElement("h3");
    title.textContent = "Bundle export CS2";

    var actions = document.createElement("div");
    actions.className = "cs2-helper-actions";

    var copyButton = document.createElement("button");
    copyButton.id = "copy-cs2-export-bundle";
    copyButton.type = "button";
    copyButton.textContent = "Copier";

    var downloadButton = document.createElement("button");
    downloadButton.id = "download-cs2-export-bundle";
    downloadButton.type = "button";
    downloadButton.textContent = "Télécharger";

    var output = document.createElement("pre");
    output.id = "cs2-helper-export-bundle";
    output.className = "cs2-helper-output";

    actions.appendChild(copyButton);
    actions.appendChild(downloadButton);

    section.appendChild(title);
    section.appendChild(actions);
    section.appendChild(output);

    container.insertBefore(section, configBlock.nextSibling);

    copyButton.addEventListener("click", function () {
      copyText(context.currentExportBundleManifest || "", function () {
        flashButton(copyButton, "Copié");
      });
    });

    downloadButton.addEventListener("click", function () {
      downloadExportBundleManifest(context);
      flashButton(downloadButton, "Téléchargé");
    });
  }
  function fallbackCopy(text) {
    var field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "readonly");
    field.style.position = "fixed";
    field.style.left = "-9999px";
    document.body.appendChild(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }

  function copyText(text, onDone) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(onDone).catch(function () {
        fallbackCopy(text);
        onDone();
      });
      return;
    }

    fallbackCopy(text);
    onDone();
  }

  function flashButton(button, label) {
    if (!button) {
      return;
    }
    var original = button.textContent;
    button.textContent = label;
    window.setTimeout(function () {
      button.textContent = original;
    }, 1100);
  }

  function syncInputs(context, state) {
    if (document.activeElement !== context.worldSizeInput) {
      context.worldSizeInput.value = formatNumber(state.worldMapSizeKm, 3);
    }
    if (document.activeElement !== context.heightmapSizeInput) {
      context.heightmapSizeInput.value = formatNumber(state.heightmapSizeKm, 3);
    }
    if (document.activeElement !== context.stepSelect) {
      context.stepSelect.value = String(state.stepMeters);
    }
  }


  function buildTimelineConfig(state) {
    var centerLat = roundNumber(state.center.lat, 6);
    var centerLon = roundNumber(state.center.lng, 6);
    var worldScale = CS2_WORLD_SCALE;

    var config = {
      useGeoJsonCenter: false,
      originLon: centerLon,
      originLat: centerLat,
      worldOriginX: 0,
      worldOriginZ: 0,
      worldScale: worldScale,
      overlayRotationDegrees: 0,
      overlayScaleX: 1,
      overlayScaleZ: 1,
      flipX: false,
      flipZ: false,
      groundMargin: 512,
      segmentWidth: 2,
      segmentHeight: 2,
      roadSegmentWidth: 2,
      roadSegmentHeight: 2,
      pointStride: 1
    };

    return JSON.stringify(config, null, 2);
  }
  function normalizeInformationPanel(context, cityName) {
    var city = String(cityName || "").trim();

    if (context.cityNameInput) {
      context.cityNameInput.hidden = false;
      context.cityNameInput.style.display = "";
      context.cityNameInput.value = city;
    }

    if (context.stepMetersInput) {
      context.stepMetersInput.hidden = false;
      context.stepMetersInput.style.display = "";
    }

    var root =
      (context.cityNameInput && context.cityNameInput.closest("section")) ||
      (context.container) ||
      document;

    Array.prototype.forEach.call(root.querySelectorAll("h1,h2,h3,.section-title,.panel-title"), function (node) {
      if (String(node.textContent || "").trim() === "Aide CS2") {
        node.textContent = "Informations";
      }
    });

    Array.prototype.forEach.call(root.querySelectorAll(".section-meta,.panel-meta,.helper-meta,span"), function (node) {
      var value = String(node.textContent || "").trim();
      if (/^Pas\s+\d+(\.\d+)?\s*m$/i.test(value)) {
        node.hidden = true;
        node.style.display = "none";
      }
    });
  }

  function hideBackendHelperBlocks(context) {
    [
      context.commandOutput,
      context.timelineManifestOutput,
      context.timelineConfigOutput
    ].forEach(function (output) {
      var block = output && output.parentElement;
      if (block) {
        block.hidden = true;
        block.style.display = "none";
      }
    });

    [
      "cs2-helper-png-contract",
      "cs2-helper-export-bundle"
    ].forEach(function (id) {
      var output = byId(id);
      var block = output && output.parentElement;
      if (block) {
        block.remove();
      }
    });
  }

  function syncInformationPanel(context, cityName) {
    var city = String(cityName || "").trim();

    if (context.cityInput && document.activeElement !== context.cityInput) {
      context.cityInput.value = city;
    }
  }

  function update(context, state) {
    var zoom = context.map.getZoom();
    var cityName = getCityName(context.cityInput);

    context.currentWorldBBox = state.worldMapBBoxText;
    context.currentHeightmapBBox = state.heightmapBBoxText;

    if (!cityName) {
      context.currentCommand = "";
      context.currentFullBundleCommand = "";
      context.currentTimelineManifest = "";
      context.currentCs2PngContract = "";
      context.currentExportBundleManifest = "";

      syncInputs(context, state);

      if (context.bundleIdOutput && document.activeElement !== context.bundleIdOutput) {
        context.bundleIdOutput.value = "";
      }

      if (context.countryInput && document.activeElement !== context.countryInput) {
        context.countryInput.value = "";
      }

      if (context.countryCodeInput && document.activeElement !== context.countryCodeInput) {
        context.countryCodeInput.value = "";
      }

      context.currentWorldBBox = "";
      context.currentHeightmapBBox = "";

      dispatchTargetBundleUpdate(context, state, null);

      setText(context.latOutput, "-");
      setText(context.lonOutput, "-");
      setText(context.zoomOutput, "-");
      setText(context.worldBBoxOutput, "-");
      setText(context.heightmapBBoxOutput, "-");
      setText(context.commandOutput, "-");

      context.fullBundleCommandOutput = ensureFullBundleCommandUi(context);
      setText(context.fullBundleCommandOutput, "-");

      hideBackendHelperBlocks(context);
      setText(context.status, "");
      return;
    }

    var bundleMeta = getBundleMeta(context, state, cityName);
    var command = buildCommand(cityName, state.heightmapBBoxText, state, bundleMeta);
    var fullBundleCommand = buildFullBundleCommand(cityName, state, bundleMeta);
    var timelineManifest = buildTimelineManifest(cityName, state, command, bundleMeta);
    var timelineConfig = buildTimelineConfig(state);
    var cs2PngContract = buildCs2PngContractText(state, bundleMeta);
    var exportBundleManifest = buildExportBundleManifestText(state, bundleMeta);

    context.currentCommand = command;
    context.currentFullBundleCommand = fullBundleCommand;
    context.currentTimelineManifest = timelineManifest;
    context.currentTimelineConfig = timelineConfig;
    context.currentCs2PngContract = cs2PngContract;
    context.currentExportBundleManifest = exportBundleManifest;

    syncInputs(context, state);
    syncBundleUi(context, bundleMeta);
    dispatchTargetBundleUpdate(context, state, bundleMeta);
    setText(context.latOutput, formatNumber(state.center.lat, 6));
    setText(context.lonOutput, formatNumber(state.center.lng, 6));
    setText(context.zoomOutput, formatNumber(zoom, 2));
    setText(context.worldBBoxOutput, state.worldMapBBoxText);
    setText(context.heightmapBBoxOutput, state.heightmapBBoxText);
    setText(context.commandOutput, command);
    context.fullBundleCommandOutput = ensureFullBundleCommandUi(context);
    setText(context.fullBundleCommandOutput, fullBundleCommand);
    hideBackendHelperBlocks(context);
    setText(context.status, "");
  }


  function ensureFullBundleCommandUi(context) {
    var existingOutput = byId("cs2-helper-bundle-command");

    if (existingOutput) {
      var existingCopyButton = byId("copy-cs2-bundle-command");

      if (existingCopyButton && existingCopyButton.getAttribute("data-cs2-bound") !== "true") {
        existingCopyButton.setAttribute("data-cs2-bound", "true");
        existingCopyButton.addEventListener("click", function () {
          copyText(context.currentFullBundleCommand || "", function () {
            flashButton(existingCopyButton, "Copié");
          });
        });
      }

      return existingOutput;
    }

    if (!context.commandOutput) {
      return null;
    }

    var commandBlock = context.commandOutput.parentElement;
    var container = commandBlock && commandBlock.parentElement;

    if (!commandBlock || !container) {
      return null;
    }

    var section = document.createElement("section");
    section.className = "cs2-helper-generated-section";
    section.style.borderTop = "1px solid rgba(255, 255, 255, 0.12)";
    section.style.marginTop = "12px";
    section.style.paddingTop = "12px";

    var title = document.createElement("h3");
    title.textContent = "Commande bundle complet";

    var actions = document.createElement("div");
    actions.className = "cs2-helper-actions";

    var copyButton = document.createElement("button");
    copyButton.id = "copy-cs2-bundle-command";
    copyButton.type = "button";
    copyButton.textContent = "Copier";

    var output = document.createElement("pre");
    output.id = "cs2-helper-bundle-command";
    output.className = "cs2-helper-output";
    output.textContent = "";

    actions.appendChild(copyButton);
    section.appendChild(title);
    section.appendChild(actions);
    section.appendChild(output);

    container.insertBefore(section, commandBlock.nextSibling);

    copyButton.addEventListener("click", function () {
      copyText(context.currentFullBundleCommand || "", function () {
        flashButton(copyButton, "Copié");
      });
    });

    return output;
  }

  function downloadTimelineManifest(context) {
    var manifestText = context.currentTimelineManifest || "";

    if (!manifestText.trim()) {
      console.warn("[CS2 Helper] Aucun manifest TimelineMod à télécharger.");
      return;
    }

    var filename = "manifest.json";

    try {
      var manifest = JSON.parse(manifestText);
      var city = String(manifest.city || "zone-cs2")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, "-")
        .replace(/^-+|-+$/g, "");

      filename = city ? city + "_manifest.json" : "manifest.json";
    } catch (error) {
      filename = "manifest.json";
    }

    var blob = new Blob([manifestText], {
      type: "application/json;charset=utf-8"
    });

    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();

    link.remove();
    URL.revokeObjectURL(url);
  }

  function downloadTimelineConfig(context) {
    var configText = context.currentTimelineConfig || "";

    if (!configText.trim()) {
      console.warn("[CS2 Helper] Aucun config TimelineMod à télécharger.");
      return;
    }

    var city = getCityName(context.cityInput)
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

    var filename = city ? city + "_config.json" : "config.json";

    var blob = new Blob([configText], {
      type: "application/json;charset=utf-8"
    });

    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();

    link.remove();
    URL.revokeObjectURL(url);
  }
  function downloadCs2PngContract(context) {
    var contractText = context.currentCs2PngContract || "";

    if (!contractText.trim()) {
      console.warn("[CS2 Helper] Aucun contrat PNG CS2 à télécharger.");
      return;
    }

    var filename = "cs2_png_contract.json";

    try {
      var contract = JSON.parse(contractText);
      filename = "cs2_png_contract_" + contract.centerLon + "_" + contract.centerLat + ".json";
    } catch (error) {
      filename = "cs2_png_contract.json";
    }

    var blob = new Blob([contractText], {
      type: "application/json;charset=utf-8"
    });

    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();

    link.remove();
    URL.revokeObjectURL(url);
  }
  function downloadExportBundleManifest(context) {
    var bundleText = context.currentExportBundleManifest || "";

    if (!bundleText.trim()) {
      console.warn("[CS2 Helper] Aucun bundle export CS2 à télécharger.");
      return;
    }

    var filename = "cs2_export_manifest.json";

    try {
      var bundle = JSON.parse(bundleText);
      filename = "cs2_export_manifest_" + bundle.center.lon + "_" + bundle.center.lat + ".json";
    } catch (error) {
      filename = "cs2_export_manifest.json";
    }

    var blob = new Blob([bundleText], {
      type: "application/json;charset=utf-8"
    });

    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();

    link.remove();
    URL.revokeObjectURL(url);
  }
  function formatStep(stepMeters) {
    return stepMeters >= 1000 ? "1 km" : stepMeters + " m";
  }


  var COUNTRY_NAME_BY_CODE = {
    "bf": "Burkina Faso",
    "fr": "France",
    "us": "United States",
    "cz": "Czechia",
    "id": "Indonesia",
    "il": "Israel",
    "gb": "United Kingdom",
    "de": "Germany",
    "it": "Italy",
    "es": "Spain",
    "jp": "Japan",
    "cn": "China",
    "br": "Brazil",
    "mx": "Mexico",
    "au": "Australia",
    "ca": "Canada"
  };

  function titleCaseBundleSlug(value) {
    return String(value || "")
      .split("_")
      .filter(Boolean)
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function getDisplayedBundleIdFromPackData(packData) {
    var indexPath = packData ? String(packData.indexPath || "") : "";
    var match = indexPath.match(/(?:^|\/)exports\/bundles\/([^\/]+)\/geojson_pack\/reports\/layer_index\.json/i);

    if (!match) {
      return "";
    }

    return sanitizeBundleId(decodeURIComponent(match[1]));
  }

  function parseDisplayedBundleMeta(packData) {
    var bundleId = getDisplayedBundleIdFromPackData(packData);
    var match = bundleId.match(/^(.+)_([a-z]{2})_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)$/i);

    if (!match) {
      return null;
    }

    var countryCode = match[2].toLowerCase();
    var lat = Number(match[3]);
    var lng = Number(match[4]);

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return null;
    }

    return {
      id: bundleId,
      city: titleCaseBundleSlug(match[1]),
      countryCode: countryCode,
      country: COUNTRY_NAME_BY_CODE[countryCode] || countryCode.toUpperCase(),
      center: {
        lat: lat,
        lng: lng
      }
    };
  }

  function hydrateTargetFromDisplayedBundle(context) {
    if (!context || !context.packData) {
      return false;
    }

    var meta = parseDisplayedBundleMeta(context.packData);

    if (!meta) {
      return false;
    }

    if (context.cityInput) {
      context.cityInput.value = meta.city;
    }

    if (context.countryInput) {
      context.countryInput.value = meta.country;
    }

    if (context.countryCodeInput) {
      context.countryCodeInput.value = meta.countryCode;
    }

    if (context.bundleIdOutput) {
      context.bundleIdOutput.value = meta.id;
    }

    if (context.overlayController) {
      context.overlayController.setCenter(meta.center);
    }

    console.info("[CS2 Helper] Emplacement courant hydraté depuis le bundle chargé:", meta);

    return true;
  }

  function updateFromController(context) {
    update(context, context.overlayController.getState());
  }

  function bindSizeInputs(context) {
    context.worldSizeInput.addEventListener("input", function () {
      context.overlayController.setWorldMapSizeKm(context.worldSizeInput.value);
    });

    context.heightmapSizeInput.addEventListener("input", function () {
      context.overlayController.setHeightmapSizeKm(context.heightmapSizeInput.value);
    });

    context.stepSelect.addEventListener("change", function () {
      context.overlayController.setStepMeters(context.stepSelect.value);
    });

    context.cityInput.addEventListener("input", function () {
      updateFromController(context);
    });

    context.countryInput.addEventListener("input", function () {
      updateFromController(context);
    });

    context.countryCodeInput.addEventListener("input", function () {
      updateFromController(context);
    });

    context.waterLevelInput.addEventListener("input", function () {
      updateFromController(context);
    });
  }

  function bindMoveButtons(context) {
    context.moveNorth.addEventListener("click", context.overlayController.moveNorth);
    context.moveSouth.addEventListener("click", context.overlayController.moveSouth);
    context.moveEast.addEventListener("click", context.overlayController.moveEast);
    context.moveWest.addEventListener("click", context.overlayController.moveWest);
    context.syncCenter.addEventListener("click", context.overlayController.syncWithMapCenter);
    context.fitOverlay.addEventListener("click", context.overlayController.centerViewOnOverlay);
  }

  function bindLocationEvents(context) {
    window.addEventListener("cs2zoning:location-selected", function (event) {
      var detail = event && event.detail ? event.detail : {};

      if (detail.city && context.cityInput) {
        context.cityInput.value = detail.city;
      }

      if (detail.country && context.countryInput) {
        context.countryInput.value = detail.country;
      }

      if (detail.countryCode && context.countryCodeInput) {
        context.countryCodeInput.value = detail.countryCode;
      }

      updateFromController(context);
    });
  }


  function bindCopyButtons(context) {
    context.copyWorldBBox.addEventListener("click", function () {
      copyText(context.currentWorldBBox, function () {
        flashButton(context.copyWorldBBox, "Copié");
      });
    });

    context.copyHeightmapBBox.addEventListener("click", function () {
      copyText(context.currentHeightmapBBox, function () {
        flashButton(context.copyHeightmapBBox, "Copié");
      });
    });

    context.copyCommand.addEventListener("click", function () {
      copyText(context.currentCommand, function () {
        flashButton(context.copyCommand, "Copié");
      });
    });

    context.copyTimelineManifest.addEventListener("click", function () {
      copyText(context.currentTimelineManifest, function () {
        flashButton(context.copyTimelineManifest, "Copié");
      });
    });

    context.downloadTimelineManifest.addEventListener("click", function () {
      downloadTimelineManifest(context);
      flashButton(context.downloadTimelineManifest, "Téléchargé");
    });

    context.copyTimelineConfig.addEventListener("click", function () {
      copyText(context.currentTimelineConfig, function () {
        flashButton(context.copyTimelineConfig, "Copié");
      });
    });

    context.downloadTimelineConfig.addEventListener("click", function () {
      downloadTimelineConfig(context);
      flashButton(context.downloadTimelineConfig, "Téléchargé");
    });
  }

  function bind(context) {
    context.overlayController.onChange(function (state) {
      update(context, state);
    });

    context.map.on("zoomend", function () {
      updateFromController(context);
    });

    bindSizeInputs(context);
    bindMoveButtons(context);
    bindLocationEvents(context);
    bindCopyButtons(context);
  }

  function create(options) {
    var mapController = options && options.mapController;
    var overlayController = options && options.overlayController;
    var context = {
      map: mapController && mapController.map,
      overlayController: overlayController,
      status: byId("cs2-helper-status"),
      packData: options.packData || null,
      cityInput: byId("cs2-helper-city"),
      countryInput: byId("cs2-helper-country"),
      countryCodeInput: byId("cs2-helper-country-code"),
      waterLevelInput: byId("cs2-helper-water-level"),
      bundleIdOutput: byId("cs2-helper-bundle-id"),
      worldSizeInput: byId("cs2-helper-size"),
      heightmapSizeInput: byId("cs2-helper-heightmap-size"),
      stepSelect: byId("cs2-helper-step"),
      latOutput: byId("cs2-helper-lat"),
      lonOutput: byId("cs2-helper-lon"),
      zoomOutput: byId("cs2-helper-zoom"),
      worldBBoxOutput: byId("cs2-helper-bbox"),
      heightmapBBoxOutput: byId("cs2-helper-heightmap-bbox"),
      commandOutput: byId("cs2-helper-command"),
      timelineManifestOutput: byId("cs2-helper-timeline-manifest"),
      timelineConfigOutput: byId("cs2-helper-timeline-config"),
      moveNorth: byId("cs2-move-north"),
      moveSouth: byId("cs2-move-south"),
      moveEast: byId("cs2-move-east"),
      moveWest: byId("cs2-move-west"),
      syncCenter: byId("sync-cs2-overlay"),
      fitOverlay: byId("fit-cs2-overlay"),
      copyWorldBBox: byId("copy-cs2-bbox"),
      copyHeightmapBBox: byId("copy-cs2-heightmap-bbox"),
      copyCommand: byId("copy-cs2-command"),
      copyTimelineManifest: byId("copy-cs2-timeline-manifest"),
      downloadTimelineManifest: byId("download-cs2-timeline-manifest"),
      copyTimelineConfig: byId("copy-cs2-timeline-config"),
      downloadTimelineConfig: byId("download-cs2-timeline-config"),
      currentWorldBBox: "",
      currentHeightmapBBox: "",
      currentCommand: "",
      currentCs2PngContract: ""
    };

    if (!context.map ||
      !context.overlayController ||
      !context.cityInput ||
      !context.countryInput ||
      !context.countryCodeInput ||
      !context.waterLevelInput ||
      !context.bundleIdOutput ||
      !context.worldSizeInput ||
      !context.heightmapSizeInput ||
      !context.stepSelect ||
      !context.worldBBoxOutput ||
      !context.heightmapBBoxOutput ||
      !context.commandOutput ||
      !context.timelineManifestOutput ||
      !context.timelineConfigOutput ||
      !context.moveNorth ||
      !context.moveSouth ||
      !context.moveEast ||
      !context.moveWest ||
      !context.syncCenter ||
      !context.fitOverlay ||
      !context.copyWorldBBox ||
      !context.copyHeightmapBBox ||
      !context.copyCommand) {
      return null;
    }

    bind(context);
    hydrateTargetFromDisplayedBundle(context);
    updateFromController(context);

    return {
      update: function () {
        updateFromController(context);
      }
    };
  }

  App.CS2MapHelper = {
    create: create
  };
})(window.CS2Zoning = window.CS2Zoning || {});

