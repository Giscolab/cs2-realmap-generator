(function (App) {
  "use strict";

  var PANE_NAME = "railway-overlay-pane";
  var CHUNK_SIZE = 350;
  var NO_DATA_MESSAGE = "Aucune donnée ferroviaire disponible dans ce bundle.";
  var SERVICE_VALUES = {
    yard: true,
    siding: true,
    spur: true,
    crossover: true
  };
  var CATEGORY_KEYS = ["train", "tram", "light_rail", "subway", "service"];
  var CATEGORIES = {
    train: {
      label: "Train",
      color: "#f8fafc",
      weightScale: 1
    },
    tram: {
      label: "Tramway",
      color: "#f59e0b",
      weightScale: 0.82
    },
    light_rail: {
      label: "Métro léger",
      color: "#22d3ee",
      weightScale: 0.92
    },
    subway: {
      label: "Métro",
      color: "#a78bfa",
      weightScale: 0.92
    },
    service: {
      label: "Voies de service",
      color: "#94a3b8",
      weightScale: 0.62
    }
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function formatNumber(value) {
    if (App.Stats && App.Stats.formatNumber) {
      return App.Stats.formatNumber(value);
    }
    return Number(value || 0).toLocaleString("fr-FR");
  }

  function normalize(value) {
    return value === null || value === undefined
      ? ""
      : String(value).replace(/^\s+|\s+$/g, "").toLowerCase();
  }

  function readProperty(properties, key) {
    if (!properties || typeof properties !== "object") {
      return undefined;
    }

    if (Object.prototype.hasOwnProperty.call(properties, key)) {
      return properties[key];
    }

    var tags = properties.tags;
    if (tags && typeof tags === "object" && Object.prototype.hasOwnProperty.call(tags, key)) {
      return tags[key];
    }

    return undefined;
  }

  function hasMeaningfulValue(value) {
    var normalized = normalize(value);
    return normalized !== "" && normalized !== "no" && normalized !== "false" && normalized !== "0" && normalized !== "none";
  }

  function isInactive(properties) {
    var status = normalize(readProperty(properties, "status"));
    var lifecycle = ["abandoned", "disused", "proposed", "construction"];

    if (status === "abandoned" || status === "disused" || status === "proposed" || status === "construction") {
      return true;
    }

    for (var i = 0; i < lifecycle.length; i += 1) {
      var key = lifecycle[i];
      if (
        hasMeaningfulValue(readProperty(properties, key)) ||
        hasMeaningfulValue(readProperty(properties, key + ":railway")) ||
        hasMeaningfulValue(readProperty(properties, "railway:" + key))
      ) {
        return true;
      }
    }

    var active = readProperty(properties, "active");
    if (active !== undefined && !hasMeaningfulValue(active)) {
      return true;
    }

    return false;
  }

  function classifyProperties(properties) {
    if (isInactive(properties)) {
      return null;
    }

    var railway = normalize(readProperty(properties, "railway"));
    var service = normalize(readProperty(properties, "service"));

    if (SERVICE_VALUES[service]) {
      if (railway === "rail" || railway === "narrow_gauge" || railway === "tram" || railway === "light_rail" || railway === "subway") {
        return "service";
      }
      return null;
    }

    if (railway === "rail" || railway === "narrow_gauge") {
      return "train";
    }
    if (railway === "tram") {
      return "tram";
    }
    if (railway === "light_rail") {
      return "light_rail";
    }
    if (railway === "subway") {
      return "subway";
    }

    return null;
  }

  function lonLatToLatLng(coordinate) {
    if (!Array.isArray(coordinate) || coordinate.length < 2) {
      return null;
    }

    var longitude = Number(coordinate[0]);
    var latitude = Number(coordinate[1]);

    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180
    ) {
      return null;
    }

    return [latitude, longitude];
  }

  function convertLine(coordinates) {
    if (!Array.isArray(coordinates)) {
      return [];
    }

    return coordinates.map(lonLatToLatLng).filter(Boolean);
  }

  function GeoRailwayLine(feature, coordinates, category) {
    var properties = feature.properties && typeof feature.properties === "object"
      ? feature.properties
      : {};

    this.id = feature.id || readProperty(properties, "id") || "";
    this.latLngs = coordinates;
    this.properties = properties;
    this.category = category;
    this.railway = normalize(readProperty(properties, "railway"));
    this.service = normalize(readProperty(properties, "service"));
    this.tunnel = hasMeaningfulValue(readProperty(properties, "tunnel"));
  }

  function parseFeature(feature) {
    if (!feature || !feature.geometry) {
      return [];
    }

    var properties = feature.properties && typeof feature.properties === "object"
      ? feature.properties
      : {};
    var category = classifyProperties(properties);

    if (!category) {
      return [];
    }

    var geometry = feature.geometry;
    var sourceLines = [];

    if (geometry.type === "LineString") {
      sourceLines = [geometry.coordinates];
    } else if (geometry.type === "MultiLineString" && Array.isArray(geometry.coordinates)) {
      sourceLines = geometry.coordinates;
    } else {
      return [];
    }

    return sourceLines.map(convertLine).filter(function (coordinates) {
      return coordinates.length >= 2;
    }).map(function (coordinates) {
      return new GeoRailwayLine(feature, coordinates, category);
    });
  }

  function parseFeatureCollection(collection) {
    if (!collection || collection.type !== "FeatureCollection" || !Array.isArray(collection.features)) {
      throw new Error("Le fichier ferroviaire n'est pas un FeatureCollection GeoJSON valide.");
    }

    return collection.features.reduce(function (lines, feature) {
      return lines.concat(parseFeature(feature));
    }, []);
  }

  function emptyCounts() {
    return {
      train: 0,
      tram: 0,
      light_rail: 0,
      subway: 0,
      service: 0,
      tunnels: 0,
      total: 0
    };
  }

  function countLines(lines) {
    var counts = emptyCounts();

    lines.forEach(function (line) {
      counts[line.category] += 1;
      counts.total += 1;
      if (line.tunnel) {
        counts.tunnels += 1;
      }
    });

    return counts;
  }

  function getRailwayPath(packIndexPath) {
    var normalized = String(packIndexPath || "").replace(/\\/g, "/");
    var marker = "/reports/";
    var markerIndex = normalized.indexOf(marker);

    if (markerIndex < 0) {
      return "";
    }

    return normalized.slice(0, markerIndex + 1) + "geojson/railways.geojson";
  }

  function fetchRailwayGeoJSON(path, fetchImplementation) {
    return fetchImplementation(path, { cache: "no-store" }).then(function (response) {
      if (response.status === 404) {
        return {
          available: false,
          reason: "missing",
          geojson: null
        };
      }
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json().then(function (geojson) {
        return {
          available: true,
          reason: "loaded",
          geojson: geojson
        };
      });
    });
  }

  function createPane(map) {
    if (!map.getPane(PANE_NAME)) {
      var pane = map.createPane(PANE_NAME);
      pane.style.zIndex = "421";
    }
  }

  function createGroups() {
    var groups = {};

    CATEGORY_KEYS.forEach(function (key) {
      groups[key] = {
        surface: L.layerGroup(),
        tunnel: L.layerGroup()
      };
    });

    return groups;
  }

  function clearGroups(context) {
    if (!context.groups) {
      return;
    }

    CATEGORY_KEYS.forEach(function (key) {
      ["surface", "tunnel"].forEach(function (kind) {
        var group = context.groups[key][kind];
        if (context.map.hasLayer(group)) {
          context.map.removeLayer(group);
        }
        group.clearLayers();
      });
    });

    context.groups = null;
    context.shapes = [];
  }

  function setGroupVisible(context, group, visible) {
    var isVisible = context.map.hasLayer(group);

    if (visible && !isVisible) {
      group.addTo(context.map);
    } else if (!visible && isVisible) {
      context.map.removeLayer(group);
    }
  }

  function syncVisibility(context) {
    if (!context.groups) {
      return;
    }

    CATEGORY_KEYS.forEach(function (key) {
      var categoryVisible = context.state.visible && context.state.categories[key];
      setGroupVisible(context, context.groups[key].surface, categoryVisible);
      setGroupVisible(context, context.groups[key].tunnel, categoryVisible && context.state.tunnels);
    });

    if (context.controls) {
      context.controls.classList.toggle("is-network-hidden", !context.state.visible);
    }
  }

  function lineStyle(context, line) {
    var definition = CATEGORIES[line.category];
    var thickness = context.state.thickness * definition.weightScale;

    return {
      pane: PANE_NAME,
      color: definition.color,
      opacity: context.state.opacity * (line.tunnel ? 0.48 : 1),
      weight: Math.max(0.5, thickness),
      dashArray: line.tunnel ? "5 7" : null,
      lineCap: "round",
      lineJoin: "round",
      interactive: true
    };
  }

  function createPopupFact(label, value) {
    if (value === null || value === undefined || String(value).trim() === "") {
      return null;
    }

    var row = document.createElement("div");
    var term = document.createElement("dt");
    var description = document.createElement("dd");
    term.textContent = label;
    description.textContent = String(value);
    row.append(term, description);
    return row;
  }

  function createPopup(line) {
    var properties = line.properties;
    var category = CATEGORIES[line.category];
    var article = document.createElement("article");
    var badge = document.createElement("span");
    var title = document.createElement("h3");
    var note = document.createElement("p");
    var facts = document.createElement("dl");
    var factValues = [
      ["Type OSM", line.railway],
      ["Usage", readProperty(properties, "usage")],
      ["Service", line.service],
      ["Voies", readProperty(properties, "tracks")],
      ["Écartement", readProperty(properties, "gauge")],
      ["Électrification", readProperty(properties, "electrified")],
      ["Tunnel", line.tunnel ? "oui" : "non"],
      ["Pont", hasMeaningfulValue(readProperty(properties, "bridge")) ? "oui" : "non"],
      ["ID OSM", line.id]
    ];

    article.className = "cs2-popup railway-popup";
    badge.className = "popup-badge";
    badge.style.setProperty("--popup-color", category.color);
    badge.textContent = category.label;
    title.className = "popup-title";
    title.textContent = readProperty(properties, "name") || "Voie ferroviaire sans nom";
    note.className = "popup-line railway-popup-note";
    note.textContent = "Plan visuel projeté sur le terrain — aucun placement automatique.";
    facts.className = "railway-popup-facts";

    factValues.forEach(function (entry) {
      var row = createPopupFact(entry[0], entry[1]);
      if (row) {
        facts.appendChild(row);
      }
    });

    article.append(badge, title, note, facts);
    return article;
  }

  function addLineToMap(context, line) {
    var shape = L.polyline(line.latLngs, lineStyle(context, line));
    var group = context.groups[line.category][line.tunnel ? "tunnel" : "surface"];

    shape.bindPopup(createPopup(line), {
      maxWidth: 340,
      minWidth: 240,
      closeButton: true
    });
    shape.addTo(group);
    context.shapes.push({ line: line, shape: shape });
  }

  function updateStyles(context) {
    context.shapes.forEach(function (entry) {
      entry.shape.setStyle(lineStyle(context, entry.line));
    });
  }

  function scheduleFrame(callback) {
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(callback);
    } else {
      window.setTimeout(callback, 0);
    }
  }

  function renderInChunks(context, lines, generation) {
    var cursor = 0;

    return new Promise(function (resolve, reject) {
      function renderChunk() {
        if (generation !== context.generation) {
          resolve(false);
          return;
        }

        try {
          var limit = Math.min(cursor + CHUNK_SIZE, lines.length);
          while (cursor < limit) {
            addLineToMap(context, lines[cursor]);
            cursor += 1;
          }
        } catch (error) {
          reject(error);
          return;
        }

        if (context.status) {
          context.status.textContent = "Affichage " + formatNumber(cursor) + " / " + formatNumber(lines.length);
        }

        if (cursor < lines.length) {
          scheduleFrame(renderChunk);
        } else {
          resolve(true);
        }
      }

      renderChunk();
    });
  }

  function updateCounts(context, counts) {
    var ids = {
      train: "railway-count-train",
      tram: "railway-count-tram",
      light_rail: "railway-count-light-rail",
      subway: "railway-count-subway",
      service: "railway-count-service",
      tunnels: "railway-count-tunnels",
      total: "railway-count-total"
    };

    Object.keys(ids).forEach(function (key) {
      var element = byId(ids[key]);
      if (element) {
        element.textContent = formatNumber(counts[key]);
      }
    });
  }

  function updateControlValues(context) {
    if (context.visibleInput) {
      context.visibleInput.checked = context.state.visible;
    }
    if (context.tunnelsInput) {
      context.tunnelsInput.checked = context.state.tunnels;
    }
    if (context.opacityInput) {
      context.opacityInput.value = String(Math.round(context.state.opacity * 100));
    }
    if (context.opacityValue) {
      context.opacityValue.textContent = Math.round(context.state.opacity * 100) + " %";
    }
    if (context.thicknessInput) {
      context.thicknessInput.value = String(context.state.thickness);
    }
    if (context.thicknessValue) {
      context.thicknessValue.textContent = context.state.thickness.toLocaleString("fr-FR") + " px";
    }

    context.categoryInputs.forEach(function (input) {
      input.checked = Boolean(context.state.categories[input.dataset.railwayCategory]);
    });
  }

  function setAvailable(context, available, message) {
    if (context.controls) {
      context.controls.disabled = !available;
    }
    if (context.message) {
      context.message.hidden = available;
      context.message.textContent = message || "";
    }
  }

  function setUnavailable(context, message, status) {
    context.generation += 1;
    clearGroups(context);
    context.lines = [];
    updateCounts(context, emptyCounts());
    setAvailable(context, false, message);
    if (context.status) {
      context.status.textContent = status || "Indisponible";
    }
  }

  function fitRailwayBounds(context, lines) {
    if (!context.fitWhenLoaded || !lines.length) {
      return;
    }

    var bounds = L.latLngBounds([]);
    lines.forEach(function (line) {
      line.latLngs.forEach(function (latLng) {
        bounds.extend(latLng);
      });
    });

    if (bounds.isValid()) {
      context.map.fitBounds(bounds, { padding: [34, 34], maxZoom: 15 });
    }
  }

  function noteRailwayDataAvailable(context, lineCount) {
    var emptyState = byId("empty-state");
    if (emptyState && lineCount > 0) {
      emptyState.hidden = true;
    }
  }

  function loadRailways(context) {
    var path = getRailwayPath(context.packIndexPath);

    if (!path) {
      setUnavailable(
        context,
        "Chargez un bundle pour afficher le réseau ferroviaire.",
        "En attente"
      );
      return Promise.resolve(null);
    }

    if (context.status) {
      context.status.textContent = "Chargement…";
    }
    setAvailable(context, false, "Chargement des données ferroviaires…");

    return fetchRailwayGeoJSON(path, window.fetch.bind(window)).then(function (result) {
      if (!result.available) {
        setUnavailable(
          context,
          NO_DATA_MESSAGE,
          "Aucune donnée"
        );
        return null;
      }

      var lines = parseFeatureCollection(result.geojson);
      var counts = countLines(lines);

      if (!lines.length) {
        setUnavailable(
          context,
          NO_DATA_MESSAGE,
          "Aucune donnée"
        );
        return null;
      }

      context.generation += 1;
      var generation = context.generation;
      clearGroups(context);
      context.groups = createGroups();
      context.lines = lines;
      syncVisibility(context);
      updateCounts(context, counts);
      setAvailable(context, true, "");

      return renderInChunks(context, lines, generation).then(function (completed) {
        if (!completed) {
          return null;
        }
        if (context.status) {
          context.status.textContent = formatNumber(counts.total) + " voie" + (counts.total > 1 ? "s" : "");
        }
        fitRailwayBounds(context, lines);
        noteRailwayDataAvailable(context, counts.total);
        return counts;
      });
    }).then(null, function (error) {
      console.warn("[RailwayController] Le calque ferroviaire optionnel n'a pas pu être chargé.", error);
      setUnavailable(
        context,
        "Données ferroviaires indisponibles ou illisibles. Le bundle reste utilisable.",
        "Indisponible"
      );
      return null;
    });
  }

  function showAllRailways(context) {
    context.state.visible = true;
    context.state.tunnels = true;
    CATEGORY_KEYS.forEach(function (key) {
      context.state.categories[key] = true;
    });
    updateControlValues(context);
    syncVisibility(context);
  }

  function hideAllRailways(context) {
    context.state.visible = false;
    updateControlValues(context);
    syncVisibility(context);
  }

  function bindControls(context) {
    if (context.visibleInput) {
      context.visibleInput.addEventListener("change", function () {
        context.state.visible = context.visibleInput.checked;
        syncVisibility(context);
      });
    }

    if (context.opacityInput) {
      context.opacityInput.addEventListener("input", function () {
        context.state.opacity = Number(context.opacityInput.value) / 100;
        updateControlValues(context);
        updateStyles(context);
      });
    }

    if (context.thicknessInput) {
      context.thicknessInput.addEventListener("input", function () {
        context.state.thickness = Number(context.thicknessInput.value);
        updateControlValues(context);
        updateStyles(context);
      });
    }

    if (context.tunnelsInput) {
      context.tunnelsInput.addEventListener("change", function () {
        context.state.tunnels = context.tunnelsInput.checked;
        syncVisibility(context);
      });
    }

    context.categoryInputs.forEach(function (input) {
      input.addEventListener("change", function () {
        context.state.categories[input.dataset.railwayCategory] = input.checked;
        syncVisibility(context);
      });
    });

    var showAll = byId("show-all-layers");
    var hideAll = byId("hide-all-layers");

    if (showAll) {
      showAll.addEventListener("click", function () {
        showAllRailways(context);
      });
    }
    if (hideAll) {
      hideAll.addEventListener("click", function () {
        hideAllRailways(context);
      });
    }
  }

  function create(options) {
    if (typeof L === "undefined") {
      throw new Error("Leaflet n'est pas chargé.");
    }
    if (!options || !options.map) {
      throw new Error("La carte Leaflet est requise pour le calque ferroviaire.");
    }

    createPane(options.map);

    var context = {
      map: options.map,
      packIndexPath: options.packIndexPath || "",
      fitWhenLoaded: Boolean(options.fitWhenLoaded),
      controls: byId("railway-controls"),
      message: byId("railway-message"),
      status: byId("railway-status"),
      visibleInput: byId("railway-visible"),
      opacityInput: byId("railway-opacity"),
      opacityValue: byId("railway-opacity-value"),
      thicknessInput: byId("railway-thickness"),
      thicknessValue: byId("railway-thickness-value"),
      tunnelsInput: byId("railway-tunnels"),
      categoryInputs: Array.prototype.slice.call(document.querySelectorAll("[data-railway-category]")),
      groups: null,
      lines: [],
      shapes: [],
      generation: 0,
      state: {
        visible: true,
        opacity: 0.9,
        thickness: 3,
        tunnels: true,
        categories: {
          train: true,
          tram: true,
          light_rail: true,
          subway: true,
          service: true
        }
      }
    };

    return {
      render: function () {
        bindControls(context);
        updateControlValues(context);
        updateCounts(context, emptyCounts());
        return loadRailways(context);
      },
      getState: function () {
        return {
          visible: context.state.visible,
          opacity: context.state.opacity,
          thickness: context.state.thickness,
          tunnels: context.state.tunnels,
          categories: Object.assign({}, context.state.categories),
          lines: context.lines.slice()
        };
      }
    };
  }

  App.RailwayController = {
    create: create,
    classifyProperties: classifyProperties,
    parseFeatureCollection: parseFeatureCollection,
    getRailwayPath: getRailwayPath,
    countLines: countLines,
    fetchRailwayGeoJSON: fetchRailwayGeoJSON,
    noDataMessage: NO_DATA_MESSAGE
  };
})(window.CS2Zoning = window.CS2Zoning || {});
