"use strict";

var assert = require("assert");

global.window = { CS2Zoning: {} };
require("../visualizer/js/cs2-command-builder.js");

var builder = global.window.CS2Zoning.CS2CommandBuilder;
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

assert.ok(command.indexOf('$ErrorActionPreference = "Stop"') >= 0);
assert.ok(command.indexOf("function Assert-PythonSuccess") >= 0);
assert.ok(command.indexOf('Assert-PythonSuccess "Extraction GeoJSON"') >= 0);
assert.ok(command.indexOf('Assert-PythonSuccess "Génération des PNG"') >= 0);
assert.ok(command.indexOf('Assert-PythonSuccess "Écriture du manifeste"') >= 0);
assert.ok(command.indexOf('Assert-PythonSuccess "Validation des PNG"') >= 0);
assert.ok(command.indexOf('python" ".\\tools\\validate_cs2_bundle.py"') >= 0);
assert.ok(command.indexOf('Assert-PythonSuccess "Validation intégrale du bundle"') >= 0);
assert.ok(command.indexOf('python" ".\\tools\\sync_citytimeline_bundle.py"') >= 0);
assert.ok(command.indexOf('Assert-PythonSuccess "Synchronisation atomique vers CityTimelineMod"') >= 0);
assert.ok(command.indexOf("  --target-root $timelineBundles `") >= 0);
assert.ok(command.indexOf("Copy-Item") < 0);
assert.ok(command.indexOf("bundle_index.json") < command.indexOf("sync_citytimeline_bundle.py"));
assert.ok(command.endsWith("tree $bundle /F"));

console.log("CS2 full bundle command tests: OK");
