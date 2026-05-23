(function (App) {
  "use strict";

  var SOURCE_READERS = {
    DATA_RESIDENTIAL: function () {
      return typeof DATA_RESIDENTIAL === "undefined" ? [] : DATA_RESIDENTIAL;
    },
    DATA_COMMERCIAL: function () {
      return typeof DATA_COMMERCIAL === "undefined" ? [] : DATA_COMMERCIAL;
    },
    DATA_RETAIL: function () {
      return typeof DATA_RETAIL === "undefined" ? [] : DATA_RETAIL;
    },
    DATA_INDUSTRIAL: function () {
      return typeof DATA_INDUSTRIAL === "undefined" ? [] : DATA_INDUSTRIAL;
    },
    DATA_PARKING: function () {
      return typeof DATA_PARKING === "undefined" ? [] : DATA_PARKING;
    },
    DATA_OFFICE: function () {
      return typeof DATA_OFFICE === "undefined" ? [] : DATA_OFFICE;
    },
    DATA_MIXED: function () {
      return typeof DATA_MIXED === "undefined" ? [] : DATA_MIXED;
    },
    DATA_ROADS: function () {
      return typeof DATA_ROADS === "undefined" ? [] : DATA_ROADS;
    },
    DATA_PATHS: function () {
      return typeof DATA_PATHS === "undefined" ? [] : DATA_PATHS;
    }
  };

  function toArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function readGlobalArray(globalName) {
    var reader = SOURCE_READERS[globalName];
    return reader ? toArray(reader()) : [];
  }

  function readSourceData(source, packData) {
    if (
      packData &&
      packData.sources &&
      Object.prototype.hasOwnProperty.call(packData.sources, source.key)
    ) {
      return toArray(packData.sources[source.key]);
    }

    return readGlobalArray(source.globalName);
  }

  function normalizeCoord(coord) {
    if (!Array.isArray(coord) || coord.length < 2) {
      return null;
    }

    var lat = Number(coord[0]);
    var longitude = Number(coord[1]);

    if (!Number.isFinite(lat) || !Number.isFinite(longitude)) {
      return null;
    }

    if (lat < -90 || lat > 90 || longitude < -180 || longitude > 180) {
      return null;
    }

    return [lat, longitude];
  }

  function normalizeCoords(coords) {
    if (!Array.isArray(coords)) {
      return [];
    }

    return coords.map(normalizeCoord).filter(Boolean);
  }

  function extendBounds(bounds, coords) {
    coords.forEach(function (coord) {
      var lat = coord[0];
      var longitude = coord[1];

      bounds.south = Math.min(bounds.south, lat);
      bounds.west = Math.min(bounds.west, longitude);
      bounds.north = Math.max(bounds.north, lat);
      bounds.east = Math.max(bounds.east, longitude);
      bounds.valid = true;
    });
  }

  function featureMatchesLayer(feature, layer) {
    if (layer.zone && feature.zone !== layer.zone) {
      return false;
    }

    if (layer.subcategory && feature.subcategory !== layer.subcategory) {
      return false;
    }

    return true;
  }

  function minimumCoordCount(layer) {
    return layer.geometry === "line" ? 2 : 3;
  }

  function createDataset(config, packData) {
    var sources = {};
    var missingSources = [];
    var bounds = {
      south: Infinity,
      west: Infinity,
      north: -Infinity,
      east: -Infinity,
      valid: false
    };

    config.dataSources.forEach(function (source) {
      var data = readSourceData(source, packData);

      sources[source.key] = {
        key: source.key,
        globalName: source.globalName,
        label: source.label,
        features: data,
        count: data.length,
        missing: data.length === 0
      };

      if (!data.length) {
        missingSources.push(source.globalName);
      }
    });

    var layers = config.layers.map(function (layer) {
      var source = sources[layer.source] || { features: [], count: 0 };

      var rawFeatures = source.features.filter(function (feature) {
        return featureMatchesLayer(feature, layer);
      });

      var features = rawFeatures.map(function (feature) {
        var coords = normalizeCoords(feature.coords);

        if (coords.length < minimumCoordCount(layer)) {
          return null;
        }

        extendBounds(bounds, coords);

        return {
          layer: layer,
          feature: feature,
          coords: coords
        };
      }).filter(Boolean);

      return {
        definition: layer,
        source: source,
        rawCount: rawFeatures.length,
        count: features.length,
        features: features,
        active: true
      };
    });

    var totalRaw = Object.keys(sources).reduce(function (total, key) {
      return total + sources[key].count;
    }, 0);

    var totalRenderable = layers.reduce(function (total, layer) {
      return total + layer.count;
    }, 0);

    return {
      dataMode: packData && packData.mode ? packData.mode : "legacy",
      packIndexPath: packData ? packData.indexPath : null,
      sources: sources,
      layers: layers,
      totalRaw: totalRaw,
      totalRenderable: totalRenderable,
      hasData: totalRaw > 0,
      hasRenderableData: totalRenderable > 0 && bounds.valid,
      missingSources: missingSources,
      bounds: bounds.valid ? [[bounds.south, bounds.west], [bounds.north, bounds.east]] : null
    };
  }

  App.DataAdapter = {
    createDataset: createDataset
  };
})(window.CS2Zoning = window.CS2Zoning || {});
