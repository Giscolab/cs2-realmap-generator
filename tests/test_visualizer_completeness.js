"use strict";

var isNode = typeof require === "function";
var App;

if (!Array.isArray) {
  Array.isArray = function (value) {
    return Object.prototype.toString.call(value) === "[object Array]";
  };
}

if (!Array.prototype.forEach) {
  Array.prototype.forEach = function (callback) {
    for (var index = 0; index < this.length; index += 1) {
      callback(this[index], index, this);
    }
  };
}

if (!Array.prototype.map) {
  Array.prototype.map = function (callback) {
    var output = [];
    this.forEach(function (value, index, array) {
      output.push(callback(value, index, array));
    });
    return output;
  };
}

if (!Array.prototype.filter) {
  Array.prototype.filter = function (callback) {
    var output = [];
    this.forEach(function (value, index, array) {
      if (callback(value, index, array)) {
        output.push(value);
      }
    });
    return output;
  };
}

if (!Array.prototype.reduce) {
  Array.prototype.reduce = function (callback, initialValue) {
    var accumulator = initialValue;
    for (var index = 0; index < this.length; index += 1) {
      accumulator = callback(accumulator, this[index], index, this);
    }
    return accumulator;
  };
}

if (!Array.prototype.some) {
  Array.prototype.some = function (callback) {
    for (var index = 0; index < this.length; index += 1) {
      if (callback(this[index], index, this)) {
        return true;
      }
    }
    return false;
  };
}

if (!Array.prototype.every) {
  Array.prototype.every = function (callback) {
    for (var index = 0; index < this.length; index += 1) {
      if (!callback(this[index], index, this)) {
        return false;
      }
    }
    return true;
  };
}

if (!Array.prototype.find) {
  Array.prototype.find = function (predicate) {
    for (var index = 0; index < this.length; index += 1) {
      if (predicate(this[index], index, this)) {
        return this[index];
      }
    }
    return undefined;
  };
}

if (!Object.keys) {
  Object.keys = function (value) {
    var keys = [];
    for (var key in value) {
      if (Object.prototype.hasOwnProperty.call(value, key)) {
        keys.push(key);
      }
    }
    return keys;
  };
}

if (!Number.isFinite) {
  Number.isFinite = function (value) {
    return typeof value === "number" && isFinite(value);
  };
}

if (!Object.assign) {
  Object.assign = function (target) {
    for (var argumentIndex = 1; argumentIndex < arguments.length; argumentIndex += 1) {
      var source = arguments[argumentIndex] || {};
      for (var key in source) {
        if (Object.prototype.hasOwnProperty.call(source, key)) {
          target[key] = source[key];
        }
      }
    }
    return target;
  };
}

if (isNode) {
  global.window = { CS2Zoning: {} };
  require("../visualizer/js/config.js");
  require("../visualizer/js/pack-loader.js");
  require("../visualizer/js/data-adapter.js");
  require("../visualizer/js/stats.js");
  require("../visualizer/js/panel-controller.js");
  App = global.window.CS2Zoning;
} else {
  var window = { CS2Zoning: {} };
  var fileSystem = new ActiveXObject("Scripting.FileSystemObject");
  [
    "visualizer\\js\\config.js",
    "visualizer\\js\\pack-loader.js",
    "visualizer\\js\\data-adapter.js",
    "visualizer\\js\\stats.js",
    "visualizer\\js\\panel-controller.js"
  ].forEach(function (file) {
    eval(fileSystem.OpenTextFile(file, 1).ReadAll());
  });
  App = window.CS2Zoning;
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error((message || "Valeurs différentes") + " : " + actual + " !== " + expected);
  }
}

function reportSuccess(message) {
  if (typeof console !== "undefined" && console.log) {
    console.log(message);
  } else {
    WScript.Echo(message);
  }
}

function polygon(extra) {
  return Object.assign({ coords: [[1, 2], [1, 3], [2, 3]] }, extra || {});
}

function line(extra) {
  return Object.assign({ coords: [[1, 2], [1, 3]] }, extra || {});
}

function shallowCopy(source) {
  return Object.assign({}, source);
}

var config = App.Config;
assertEqual(config.layers.length, 20, "le HUD doit exposer les 20 couches de base");
assertEqual(config.dataSources.length, 11, "les 20 couches reposent sur 11 GeoJSON de base");

var indexedSourceLayers = config.dataSources.map(function (source) {
  return { name: source.key, file: "geojson/" + source.key + ".geojson", count: 0 };
});
indexedSourceLayers.push({ name: "all_features", file: "geojson/all_features.geojson", count: 0 });
var selectedSourceLayers = App.PackLoader.selectSourceLayers(
  { layers: indexedSourceLayers },
  config
);
assertEqual(selectedSourceLayers.length, 11, "le chargeur doit sélectionner les 11 sources, même vides");
assertEqual(selectedSourceLayers.every(function (layer) {
  return layer.count === 0;
}), true, "les sources vides doivent rester sélectionnées");

var sources = {
  residential: [polygon({ zone: "high" }), polygon({ zone: "medium" }), polygon({ zone: "low" })],
  commercial: [polygon({ zone: "high" }), polygon({ zone: "low" })],
  retail: [polygon()],
  industrial: [polygon()],
  parking: [polygon({ zone: "ramp" }), polygon({ zone: "surface" })],
  office: [polygon()],
  mixed: [],
  roads: [
    line({ tags: { highway: "motorway" } }),
    line({ tags: { highway: "primary" } }),
    line({ tags: { highway: "secondary" } }),
    line({ tags: { highway: "residential" } }),
    line({ tags: { highway: "primary_link" } }),
    line({ tags: { highway: "service" } })
  ],
  paths: [
    line({ tags: { highway: "cycleway" } }),
    line({ tags: { highway: "bridleway" } }),
    line({ tags: { highway: "corridor" } }),
    line({ tags: { highway: "platform" } })
  ],
  water_lines_clipped: [],
  water_areas_clipped: []
};

var serviceKeys = [
  "education", "fire", "medical", "parks", "electricity",
  "waste", "transport", "water", "communications"
];
var families = serviceKeys.map(function (key) {
  return { key: key, count: 1 };
});

var packData = {
  mode: "pack",
  sources: sources,
  index: {
    contracts: {
      all_features: {
        includes: [
          "residential", "commercial", "industrial", "retail", "parking",
          "office", "mixed", "roads", "paths", "water_lines", "water_areas"
        ],
        excludesIndependentSources: ["railways", "services/*"]
      }
    },
    layers: [
      { name: "all_features", count: 20 },
      { name: "railways", count: 3 }
    ]
  },
  servicesIndex: { families: families }
};

var adapter = App.DataAdapter;
var dataset = adapter.createDataset(config, packData);

// Un GeoJSON présent mais vide est disponible, jamais signalé comme manquant.
["mixed", "water_lines_clipped", "water_areas_clipped"].forEach(function (key) {
  assertEqual(dataset.sources[key].available, true, key + " doit être disponible");
  assertEqual(dataset.sources[key].empty, true, key + " doit être marqué vide");
  assertEqual(dataset.sources[key].missing, false, key + " ne doit pas être marqué manquant");
});
assertEqual(dataset.missingSources.length, 0);

// 20 couches de base + 1 couche ferroviaire + 9 familles de services.
assertEqual(dataset.layers.length, 20);
assertEqual(dataset.layers.every(function (layerData) { return layerData.available; }), true);
assertEqual(dataset.layerCoverage.baseAvailable, 20);
assertEqual(dataset.layerCoverage.railwayAvailable, true);
assertEqual(dataset.layerCoverage.serviceFamiliesAvailable, 9);
assertEqual(dataset.layerCoverage.available, 30);
assertEqual(dataset.layerCoverage.expected, 30);
assertEqual(dataset.layerCoverage.complete, true);

// Les nouvelles valeurs highway restent toutes dans le filtre Chemins/piéton.
var pathLayer = dataset.layers.find(function (layerData) {
  return layerData.definition.key === "paths";
});
assertEqual(pathLayer.count, 4);
assertEqual(pathLayer.features.map(function (item) {
  return item.feature.tags.highway;
}).join(","), "cycleway,bridleway,corridor,platform");

// Total visuel : agrégat de base + sources indépendantes, une seule fois chacune.
assertEqual(dataset.totalVisualEntities, 32);
var stats = App.Stats.compute(dataset);
assertEqual(stats.total, 32);
assertEqual(stats.railways, 3);
assertEqual(stats.services, 9);

// Compatibilité : un ancien all_features qui déclare déjà rail/services ne doit
// pas provoquer un double comptage dans le total visuel.
var aggregatePack = shallowCopy(packData);
aggregatePack.index = shallowCopy(packData.index);
aggregatePack.index.contracts = {
  all_features: { includes: ["railways", "services/*"] }
};
assertEqual(adapter.createDataset(config, aggregatePack).totalVisualEntities, 20);

// Un bundle moderne partiel ne doit jamais récupérer une ancienne globale et
// afficher des géométries appartenant à un autre bundle.
if (isNode) {
  global.DATA_MIXED = [polygon()];
} else {
  DATA_MIXED = [polygon()];
}
var partialSources = shallowCopy(sources);
delete partialSources.mixed;
var partialPack = shallowCopy(packData);
partialPack.sources = partialSources;
var partial = adapter.createDataset(config, partialPack);
assertEqual(partial.sources.mixed.count, 0);
assertEqual(partial.sources.mixed.missing, true);
assertEqual(partial.layerCoverage.complete, false);

reportSuccess("Visualizer completeness contract: OK");
