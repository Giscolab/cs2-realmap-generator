"use strict";

var isNode = typeof module !== "undefined" && module.exports && typeof require === "function";
var builder;

function assertOk(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion échouée");
  }
}

if (isNode) {
  global.window = { CS2Zoning: {} };
  require("../visualizer/js/cs2-command-builder.js");
  builder = global.window.CS2Zoning.CS2CommandBuilder;
} else {
  var fso = new ActiveXObject("Scripting.FileSystemObject");
  var testDir = fso.GetParentFolderName(WScript.ScriptFullName);
  var root = fso.GetParentFolderName(testDir);
  var sourcePath = fso.BuildPath(root, "visualizer\\js\\cs2-command-builder.js");
  var stream = fso.OpenTextFile(sourcePath, 1, false);
  var source = stream.ReadAll();
  stream.Close();
  var window = { CS2Zoning: {} };
  eval(source);
  builder = window.CS2Zoning.CS2CommandBuilder;
}

var command = builder.buildFullBundleCommand({
  center: { lat: -35.281, lng: 149.128 },
  worldMapSizeKm: 57.344,
  heightmapSizeKm: 14.336,
  worldMapBBoxText: "-35.539433,148.812836,-35.022567,149.443164",
  heightmapBBoxText: "-35.345608,149.049209,-35.216392,149.206791"
}, {
  id: "canberra_au_-35.281000_149.128000",
  city: "Canberra",
  country: "Australia",
  countryCode: "au",
  dir: ".\\exports\\bundles\\canberra_au_-35.281000_149.128000"
});

assertOk(command.indexOf('$ErrorActionPreference = "Stop"') >= 0, "ErrorActionPreference absent");
assertOk(command.indexOf("function Assert-PythonSuccess") >= 0, "garde code retour absente");
assertOk(command.indexOf('python" ".\\tools\\build_complete_bundle.py"') >= 0, "orchestrateur absent");
assertOk(command.indexOf("  --bbox \"-35.539433,148.812836,-35.022567,149.443164\" `") >= 0, "bbox worldmap absente");
assertOk(command.indexOf("  --heightmap-bbox \"-35.345608,149.049209,-35.216392,149.206791\" `") >= 0, "bbox heightmap absente");
assertOk(command.indexOf("  --target-root $timelineBundles") >= 0, "destination Timeline absente");
assertOk(command.indexOf('Assert-PythonSuccess "Bundle complet : extraction, PNG, validations et synchronisation"') >= 0, "contrôle final absent");

assertOk(command.indexOf(".\\src\\extract_zoning.py") < 0, "ancienne extraction indépendante encore générée");
assertOk(command.indexOf(".\\tools\\export_cs2_pngs.py") < 0, "ancien export indépendant encore généré");
assertOk(command.indexOf(".\\tools\\write_cs2_bundle_manifest.py") < 0, "ancien manifeste indépendant encore généré");
assertOk(command.indexOf(".\\tools\\validate_cs2_bundle.py") < 0, "ancienne validation indépendante encore générée");
assertOk(command.indexOf(".\\tools\\sync_citytimeline_bundle.py") < 0, "ancienne synchronisation indépendante encore générée");
assertOk(command.indexOf("Copy-Item") < 0, "Copy-Item interdit");
assertOk(command.slice(-15) === "tree $bundle /F", "inventaire final absent");

if (isNode) {
  console.log("CS2 full bundle command tests: OK");
} else {
  WScript.Echo("CS2 full bundle command tests: OK");
}
