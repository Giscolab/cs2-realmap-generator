(function (App) {
  "use strict";

  var DEFAULT_PACK_INDEX_PATH = "../exports/bundles/irvine_ca_us_33.653495_-117.723999/geojson_pack/reports/layer_index.json";

  var SOURCE_KEYS = {
    residential: true,
    commercial: true,
    retail: true,
    industrial: true,
    parking: true,
    office: true,
    mixed: true,
    roads: true,
    paths: true,
    water_lines_clipped: true,
    water_areas_clipped: true
  };

  function fetchJSON(path) {
    return fetch(path, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("Impossible de charger " + path + " — HTTP " + response.status);
      }
      return response.json();
    });
  }

  function getPackRoot(indexPath) {
    var marker = "/reports/";
    var index = indexPath.indexOf(marker);

    if (index >= 0) {
      return indexPath.slice(0, index + 1);
    }

    return indexPath.replace(/[^/]+$/, "");
  }

  function resolveLayerPath(indexPath, layerFile) {
    if (/^https?:\/\//i.test(layerFile) || layerFile.charAt(0) === "/") {
      return layerFile;
    }

    return getPackRoot(indexPath) + layerFile;
  }

  function cloneProperties(feature) {
    var props = feature && feature.properties && typeof feature.properties === "object"
      ? feature.properties
      : {};

    var output = {};

    Object.keys(props).forEach(function (key) {
      output[key] = props[key];
    });

    return output;
  }

  function lonLatToLatLon(coord) {
    if (!Array.isArray(coord) || coord.length < 2) {
      return null;
    }

    var lon = Number(coord[0]);
    var lat = Number(coord[1]);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      return null;
    }

    return [lat, lon];
  }

  function convertLine(line) {
    if (!Array.isArray(line)) {
      return [];
    }

    return line.map(lonLatToLatLon).filter(Boolean);
  }

  function convertPolygonRing(ring) {
    var coords = convertLine(ring);

    if (coords.length > 1) {
      var first = coords[0];
      var last = coords[coords.length - 1];

      if (first[0] === last[0] && first[1] === last[1]) {
        coords.pop();
      }
    }

    return coords;
  }

  function makeItem(properties, coords) {
    var item = {};

    Object.keys(properties).forEach(function (key) {
      item[key] = properties[key];
    });

    item.coords = coords;
    return item;
  }

  function convertFeature(feature) {
    if (!feature || !feature.geometry) {
      return [];
    }

    var geometry = feature.geometry;
    var properties = cloneProperties(feature);

    if (geometry.type === "LineString") {
      return [makeItem(properties, convertLine(geometry.coordinates))];
    }

    if (geometry.type === "MultiLineString") {
      return geometry.coordinates.map(function (line) {
        return makeItem(properties, convertLine(line));
      });
    }

    if (geometry.type === "Polygon") {
      var ring = geometry.coordinates && geometry.coordinates[0];
      return [makeItem(properties, convertPolygonRing(ring))];
    }

    if (geometry.type === "MultiPolygon") {
      return geometry.coordinates.map(function (polygon) {
        var ring = polygon && polygon[0];
        return makeItem(properties, convertPolygonRing(ring));
      });
    }

    return [];
  }

  function convertFeatureCollection(collection) {
    if (!collection || collection.type !== "FeatureCollection" || !Array.isArray(collection.features)) {
      return [];
    }

    return collection.features.reduce(function (items, feature) {
      return items.concat(convertFeature(feature));
    }, []).filter(function (item) {
      return Array.isArray(item.coords) && item.coords.length > 0;
    });
  }

  function loadDefaultPack(config) {
    var indexPath = config.packIndexPath || DEFAULT_PACK_INDEX_PATH;

    return fetchJSON(indexPath).then(function (index) {
      var sourceLayers = (index.layers || []).filter(function (layer) {
        return layer && SOURCE_KEYS[layer.name] && layer.file;
      });

      return Promise.all(sourceLayers.map(function (layer) {
        var layerPath = resolveLayerPath(indexPath, layer.file);

        return fetchJSON(layerPath).then(function (geojson) {
          return {
            key: layer.name,
            file: layer.file,
            path: layerPath,
            features: convertFeatureCollection(geojson)
          };
        });
      })).then(function (loadedLayers) {
        var sources = {};

        loadedLayers.forEach(function (layer) {
          sources[layer.key] = layer.features;
        });

        var packRoot = getPackRoot(indexPath);
        var servicesIndexPath = packRoot + "reports/services_index.json";
        var roadsIndexPath = packRoot + "reports/roads_index.json";

        return Promise.all([
          fetchJSON(servicesIndexPath).catch(function () {
            return null;
          }),
          fetchJSON(roadsIndexPath).catch(function () {
            return null;
          })
        ]).then(function (indexes) {
          return {
            mode: "pack",
            indexPath: indexPath,
            index: index,
            sources: sources,
            servicesIndex: indexes[0],
            roadsIndex: indexes[1]
          };
        });
      });
    });
  }

  App.PackLoader = {
    loadDefaultPack: loadDefaultPack
  };
})(window.CS2Zoning = window.CS2Zoning || {});
