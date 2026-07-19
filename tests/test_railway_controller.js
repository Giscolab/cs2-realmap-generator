"use strict";

var isNode = typeof require === "function";
var controller;

if (!Array.prototype.forEach) {
  Array.prototype.forEach = function (callback) {
    for (var index = 0; index < this.length; index += 1) {
      callback(this[index], index, this);
    }
  };
}

if (isNode) {
  global.window = { CS2Zoning: {} };
  require("../visualizer/js/railway-controller.js");
  controller = global.window.CS2Zoning.RailwayController;
} else {
  var window = { CS2Zoning: {} };
  var fileSystem = new ActiveXObject("Scripting.FileSystemObject");
  var source = fileSystem.OpenTextFile("visualizer\\js\\railway-controller.js", 1).ReadAll();
  eval(source);
  controller = window.CS2Zoning.RailwayController;
}

var assert = {
  strictEqual: function (actual, expected) {
    if (actual !== expected) {
      throw new Error("Valeurs différentes : " + actual + " !== " + expected);
    }
  },
  deepStrictEqual: function (actual, expected) {
    var key;
    for (key in expected) {
      if (Object.prototype.hasOwnProperty.call(expected, key) && actual[key] !== expected[key]) {
        throw new Error("Valeur différente pour " + key + " : " + actual[key] + " !== " + expected[key]);
      }
    }
    for (key in actual) {
      if (Object.prototype.hasOwnProperty.call(actual, key) && !Object.prototype.hasOwnProperty.call(expected, key)) {
        throw new Error("Propriété inattendue : " + key);
      }
    }
  }
};

function reportSuccess(message) {
  if (typeof console !== "undefined" && console.log) {
    console.log(message);
  } else {
    WScript.Echo(message);
  }
}

function featureProperties(railway, extra) {
  var properties = { railway: railway };
  var additions = extra || {};
  for (var key in additions) {
    if (Object.prototype.hasOwnProperty.call(additions, key)) {
      properties[key] = additions[key];
    }
  }
  return properties;
}

function testClassification() {
  assert.strictEqual(controller.classifyProperties(featureProperties("rail")), "train");
  assert.strictEqual(controller.classifyProperties(featureProperties("narrow_gauge")), "train");
  assert.strictEqual(controller.classifyProperties(featureProperties("tram")), "tram");
  assert.strictEqual(controller.classifyProperties(featureProperties("light_rail")), "light_rail");
  assert.strictEqual(controller.classifyProperties(featureProperties("subway")), "subway");
  assert.strictEqual(controller.classifyProperties({ tags: { railway: "tram" } }), "tram");
  assert.strictEqual(controller.classifyProperties(featureProperties("monorail")), null);
  assert.strictEqual(controller.classifyProperties(featureProperties("rail", { disused: "yes" })), null);
  assert.strictEqual(controller.classifyProperties(featureProperties("rail", { construction: "rail" })), null);
  assert.strictEqual(controller.classifyProperties(featureProperties("subway", { "railway:construction": "subway" })), null);
}

function testServicePriority() {
  ["yard", "siding", "spur", "crossover"].forEach(function (service) {
    assert.strictEqual(
      controller.classifyProperties(featureProperties("rail", { service: service })),
      "service"
    );
  });

  assert.strictEqual(
    controller.classifyProperties(featureProperties("light_rail", { service: "siding" })),
    "service"
  );
  assert.strictEqual(
    controller.classifyProperties(featureProperties("rail", { service: "station" })),
    "train"
  );
}

function testCountsAreExclusive() {
  var counts = controller.countLines([
    { category: "train", tunnel: false },
    { category: "tram", tunnel: true },
    { category: "light_rail", tunnel: false },
    { category: "subway", tunnel: true },
    { category: "service", tunnel: false },
    { category: "service", tunnel: true }
  ]);

  assert.deepStrictEqual(counts, {
    train: 1,
    tram: 1,
    light_rail: 1,
    subway: 1,
    service: 2,
    tunnels: 3,
    total: 6
  });
  assert.strictEqual(
    counts.total,
    counts.train + counts.tram + counts.light_rail + counts.subway + counts.service
  );
}

function testRailwayPath() {
  assert.strictEqual(
    controller.getRailwayPath("../exports/bundles/paris/geojson_pack/reports/layer_index.json"),
    "../exports/bundles/paris/geojson_pack/geojson/railways.geojson"
  );
  assert.strictEqual(controller.getRailwayPath(""), "");
  assert.strictEqual(controller.getRailwayPath("../unexpected/index.json"), "");
}

function testLegacyBundle404() {
  var fakeFetch = function () {
    return Promise.resolve({
      ok: false,
      status: 404,
      json: function () {
        throw new Error("json() ne doit pas être appelé pour un 404");
      }
    });
  };

  return controller.fetchRailwayGeoJSON("railways.geojson", fakeFetch).then(function (result) {
    assert.deepStrictEqual(result, {
      available: false,
      reason: "missing",
      geojson: null
    });
    assert.strictEqual(
      controller.noDataMessage,
      "Aucune donnée ferroviaire disponible dans ce bundle."
    );
  });
}

testClassification();
testServicePriority();
testCountsAreExclusive();
testRailwayPath();

if (typeof Promise === "function") {
  testLegacyBundle404().then(function () {
    reportSuccess("Railway controller tests: OK");
  }).then(null, function (error) {
    console.error(error);
    process.exitCode = 1;
  });
} else {
  reportSuccess("Railway controller core tests: OK (test 404 réservé à Node)");
}
