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

  var ROAD_CATEGORY_BY_HIGHWAY = {
    motorway: "highway",
    trunk: "highway",
    primary: "large_road",
    secondary: "medium_road",
    tertiary: "small_road",
    residential: "small_road",
    living_street: "small_road",
    motorway_link: "ramp",
    trunk_link: "ramp",
    primary_link: "ramp",
    secondary_link: "ramp",
    tertiary_link: "ramp",
    pedestrian: "pathway",
    footway: "pathway",
    path: "pathway",
    steps: "pathway",
    cycleway: "pathway",
    bridleway: "pathway",
    unclassified: "gravel_road",
    service: "gravel_road",
    road: "gravel_road",
    track: "gravel_road"
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

    if (layer.roadCategory && classifyFeatureRoadCategory(feature) !== layer.roadCategory) {
      return false;
    }

    return true;
  }

  function highwayFromSourceTag(value) {
    var match = String(value || "").match(/^highway=([^;,\s]+)/i);
    return match ? match[1].toLowerCase() : "";
  }

  function classifyFeatureRoadCategory(feature) {
    if (feature && feature.roadCategory) {
      return feature.roadCategory;
    }

    var tags = feature && feature.tags && typeof feature.tags === "object" ? feature.tags : {};
    var highway = String(tags.highway || highwayFromSourceTag(feature && feature.sourceTag)).toLowerCase();
    return ROAD_CATEGORY_BY_HIGHWAY[highway] || "gravel_road";
  }

  function roadIndexByCategory(packData) {
    var categories = packData &&
      packData.roadsIndex &&
      Array.isArray(packData.roadsIndex.categories)
      ? packData.roadsIndex.categories
      : [];

    return categories.reduce(function (index, category) {
      if (category && category.key) {
        index[category.key] = category;
      }
      return index;
    }, {});
  }

  function validColor(value) {
    var color = String(value || "").trim();
    return /^#[0-9a-fA-F]{3,8}$/.test(color) ? color : "";
  }

  function applyRoadContract(layer, roadsIndex) {
    if (!layer.roadCategory || !roadsIndex[layer.roadCategory]) {
      return layer;
    }

    var category = roadsIndex[layer.roadCategory];
    var color = validColor(category.color);

    return Object.assign({}, layer, {
      label: category.label || layer.label,
      color: color || layer.color,
      stroke: color || layer.stroke || layer.color
    });
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

    var roadsIndex = roadIndexByCategory(packData);
    var layers = config.layers.map(function (baseLayer) {
      var layer = applyRoadContract(baseLayer, roadsIndex);
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

        var featureForLayer = feature;

        if (layer.roadCategory && !featureForLayer.roadColor) {
          featureForLayer = Object.assign({}, feature, {
            roadCategory: classifyFeatureRoadCategory(feature),
            roadColor: layer.color
          });
        }

        return {
          layer: layer,
          feature: featureForLayer,
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
