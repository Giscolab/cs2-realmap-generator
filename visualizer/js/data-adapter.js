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
    },
    DATA_WATER_LINES: function () {
      return typeof DATA_WATER_LINES === "undefined" ? [] : DATA_WATER_LINES;
    },
    DATA_WATER_AREAS: function () {
      return typeof DATA_WATER_AREAS === "undefined" ? [] : DATA_WATER_AREAS;
    }
  };

  var EXPECTED_SERVICE_FAMILY_COUNT = 9;

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
    corridor: "pathway",
    platform: "pathway",
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
    if (packData && packData.mode === "pack") {
      if (
        packData.sources &&
        Object.prototype.hasOwnProperty.call(packData.sources, source.key)
      ) {
        return toArray(packData.sources[source.key]);
      }

      // Ne mélange jamais un bundle moderne partiel avec d'anciennes variables
      // globales éventuellement encore présentes dans la page.
      return [];
    }

    return readGlobalArray(source.globalName);
  }

  function sourceIsAvailable(source, packData, data) {
    if (packData && packData.mode === "pack") {
      return Boolean(
        packData.sources &&
        Object.prototype.hasOwnProperty.call(packData.sources, source.key)
      );
    }

    // Les anciens packs globaux ne permettent pas de distinguer un tableau
    // volontairement vide d'une variable absente. On conserve leur comportement
    // historique, tandis que le contrat indexe explicitement cette information
    // pour les bundles modernes.
    return data.length > 0;
  }

  function indexedLayer(packData, key) {
    var layers = packData && packData.index && Array.isArray(packData.index.layers)
      ? packData.index.layers
      : [];
    return layers.find(function (entry) {
      return entry && entry.name === key;
    }) || null;
  }

  function nonNegativeCount(value) {
    var count = Number(value);
    return Number.isFinite(count) && count >= 0 ? count : 0;
  }

  function indexedLayerCount(packData, key) {
    var layer = indexedLayer(packData, key);
    var count = Number(layer && layer.count);
    return Number.isFinite(count) && count >= 0 ? count : 0;
  }

  function aggregateIncludes(packData, sourceName) {
    var contract = packData &&
      packData.index &&
      packData.index.contracts &&
      packData.index.contracts.all_features;
    var includes = contract && Array.isArray(contract.includes) ? contract.includes : [];

    return includes.some(function (entry) {
      var value = String(entry || "");
      if (sourceName === "services/*") {
        return value === "services/*" || value.indexOf("services/") === 0;
      }
      return value === sourceName;
    });
  }

  function indexedServiceCount(packData) {
    var families = packData &&
      packData.servicesIndex &&
      Array.isArray(packData.servicesIndex.families)
      ? packData.servicesIndex.families
      : [];

    return families.reduce(function (total, family) {
      return total + nonNegativeCount(family && family.count);
    }, 0);
  }

  function indexedServiceFamilyCount(packData) {
    var families = packData &&
      packData.servicesIndex &&
      Array.isArray(packData.servicesIndex.families)
      ? packData.servicesIndex.families
      : [];
    var seen = {};

    families.forEach(function (family) {
      var key = String(family && family.key || "");
      if (key) {
        seen[key] = true;
      }
    });

    return Object.keys(seen).length;
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
      var available = sourceIsAvailable(source, packData, data);

      sources[source.key] = {
        key: source.key,
        globalName: source.globalName,
        label: source.label,
        features: data,
        count: data.length,
        available: available,
        empty: available && data.length === 0,
        missing: !available
      };

      if (!available) {
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
        available: Boolean(source.available),
        empty: Boolean(source.available) && features.length === 0,
        missing: !source.available,
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
    var allFeaturesLayer = indexedLayer(packData, "all_features");
    var indexedAllFeatures = indexedLayerCount(packData, "all_features");
    var railwayLayer = indexedLayer(packData, "railways");
    var railwayCount = indexedLayerCount(packData, "railways");
    var serviceCount = indexedServiceCount(packData);
    var serviceFamilyCount = indexedServiceFamilyCount(packData);
    var allFeaturesCount = allFeaturesLayer ? indexedAllFeatures : totalRaw;
    // Compatibilité avec d'anciens agrégats : si leur contrat déclare déjà
    // rail/services dans all_features, ces sources ne sont pas recomptées.
    var independentRailwayCount = aggregateIncludes(packData, "railways") ? 0 : railwayCount;
    var independentServiceCount = aggregateIncludes(packData, "services/*") ? 0 : serviceCount;
    var availableSourceCount = Object.keys(sources).reduce(function (total, key) {
      return total + (sources[key].available ? 1 : 0);
    }, 0);
    var availableBaseLayerCount = layers.reduce(function (total, layer) {
      return total + (layer.available ? 1 : 0);
    }, 0);
    var railwayAvailable = Boolean(railwayLayer);
    var servicesIndexAvailable = Boolean(
      packData &&
      packData.servicesIndex &&
      Array.isArray(packData.servicesIndex.families)
    );
    var availableVisualLayerCount = availableBaseLayerCount +
      (railwayAvailable ? 1 : 0) + serviceFamilyCount;
    var expectedVisualLayerCount = layers.length + 1 + EXPECTED_SERVICE_FAMILY_COUNT;
    var hasBundleSources = availableSourceCount > 0 || railwayAvailable || servicesIndexAvailable;

    return {
      dataMode: packData && packData.mode ? packData.mode : "legacy",
      packIndexPath: packData ? packData.indexPath : null,
      sources: sources,
      layers: layers,
      totalRaw: totalRaw,
      totalVisualEntities: allFeaturesCount + independentRailwayCount + independentServiceCount,
      totalRenderable: totalRenderable,
      bundleTotals: {
        allFeatures: allFeaturesCount,
        railways: railwayCount,
        services: serviceCount,
        water: sourceCountSafe(sources, "water_lines_clipped") +
          sourceCountSafe(sources, "water_areas_clipped")
      },
      sourceCoverage: {
        available: availableSourceCount,
        expected: config.dataSources.length
      },
      layerCoverage: {
        available: availableVisualLayerCount,
        expected: expectedVisualLayerCount,
        baseAvailable: availableBaseLayerCount,
        baseExpected: layers.length,
        railwayAvailable: railwayAvailable,
        serviceFamiliesAvailable: serviceFamilyCount,
        serviceFamiliesExpected: EXPECTED_SERVICE_FAMILY_COUNT,
        complete: availableVisualLayerCount === expectedVisualLayerCount
      },
      hasBundleSources: hasBundleSources,
      hasData: allFeaturesCount + independentRailwayCount + independentServiceCount > 0,
      hasRenderableData: totalRenderable > 0 && bounds.valid,
      missingSources: missingSources,
      bounds: bounds.valid ? [[bounds.south, bounds.west], [bounds.north, bounds.east]] : null
    };
  }

  function sourceCountSafe(sources, key) {
    return sources[key] ? sources[key].count : 0;
  }

  App.DataAdapter = {
    createDataset: createDataset
  };
})(window.CS2Zoning = window.CS2Zoning || {});
