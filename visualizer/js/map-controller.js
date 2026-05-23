(function (App) {
  "use strict";

  function chooseFeatureColor(feature, fallback) {
    var value = App.SafeHTML.safeText(feature.color);
    if (/^#[0-9a-fA-F]{3,8}$/.test(value)) {
      return value;
    }
    return fallback;
  }

  function buildTagsHTML(tags) {
    if (!tags || typeof tags !== "object") {
      return "";
    }

    var entries = Object.keys(tags).sort().map(function (key) {
      return [key, tags[key]];
    }).filter(function (entry) {
      return entry[1] !== null && entry[1] !== undefined && String(entry[1]).trim() !== "";
    }).slice(0, 12);

    if (!entries.length) {
      return "";
    }

    return '<div class="popup-tags">' + entries.map(function (entry) {
      return '<div class="popup-tag"><span class="popup-tag-key">' +
        App.SafeHTML.escapeHTML(entry[0]) +
        '</span><span>' +
        App.SafeHTML.escapeHTML(entry[1]) +
        "</span></div>";
    }).join("") + "</div>";
  }

  function buildPopup(item) {
    var feature = item.feature;
    var layer = item.layer;
    var name = App.SafeHTML.escapeHTML(App.SafeHTML.safeText(feature.name, "Objet OSM sans nom"));
    var cs2 = App.SafeHTML.escapeHTML(App.SafeHTML.safeText(feature.cs2, layer.cs2));
    var osmId = App.SafeHTML.escapeHTML(App.SafeHTML.safeText(feature.id, "non renseigné"));
    var realWorld = App.SafeHTML.escapeHTML(layer.realWorld);
    var label = App.SafeHTML.escapeHTML(layer.label);
    var color = App.SafeHTML.escapeAttribute(layer.color);
    var tags = buildTagsHTML(feature.tags);

    return '<article class="cs2-popup">' +
      '<span class="popup-badge" style="--popup-color:' + color + ';">' + label + "</span>" +
      '<h3 class="popup-title">' + name + "</h3>" +
      '<p class="popup-line">Réalité observée : ' + realWorld + "</p>" +
      '<div class="popup-brush">' +
      '<div class="popup-brush-label">Pinceau CS2 recommandé</div>' +
      '<div class="popup-brush-value">' + cs2 + "</div>" +
      "</div>" +
      tags +
      '<div class="popup-osm">ID OSM : ' + osmId + "</div>" +
      "</article>";
  }

  function addFeatureToGroup(item, group) {
    var definition = item.layer;
    var strokeColor = chooseFeatureColor(item.feature, definition.stroke || definition.color);
    var shape;

    if (definition.geometry === "line") {
      shape = L.polyline(item.coords, {
        color: strokeColor,
        opacity: 0.92,
        weight: definition.lineWeight || 2,
        lineCap: "round",
        lineJoin: "round"
      });
    } else {
      shape = L.polygon(item.coords, {
        color: definition.stroke,
        fillColor: chooseFeatureColor(item.feature, definition.color),
        fillOpacity: 0.48,
        opacity: 0.9,
        weight: 1,
        lineJoin: "round"
      });
    }

    shape.bindPopup(buildPopup(item), {
      maxWidth: 340,
      minWidth: 240,
      closeButton: true
    });
    shape.addTo(group);
  }

  function create(options) {
    if (typeof L === "undefined") {
      throw new Error("Leaflet n'est pas chargé.");
    }

    var config = options.config;
    var dataset = options.dataset;
    var map = L.map(options.containerId, {
      zoomControl: false,
      preferCanvas: true
    }).setView(config.fallbackCenter, config.fallbackZoom);

    var tileOptions = Object.assign({}, config.tileLayer.options, {
      r: window.devicePixelRatio >= 2 ? "@2x" : ""
    });

    L.tileLayer(config.tileLayer.url, tileOptions).addTo(map);
    L.control.zoom({ position: "bottomleft" }).addTo(map);

    var groups = {};
    var layerState = {};

    dataset.layers.forEach(function (layerData) {
      var definition = layerData.definition;
      var group = L.layerGroup().addTo(map);
      groups[definition.key] = group;
      layerState[definition.key] = true;

      layerData.features.forEach(function (item) {
        addFeatureToGroup(item, group);
      });
    });

    function fitInitialBounds() {
      if (dataset.hasRenderableData && dataset.bounds) {
        map.fitBounds(dataset.bounds, { padding: [34, 34], maxZoom: 15 });
        return;
      }
      map.fitBounds(config.fallbackBounds, { padding: [24, 24] });
    }

    function setLayerVisible(key, visible) {
      var group = groups[key];
      if (!group) {
        return;
      }
      layerState[key] = Boolean(visible);
      if (layerState[key]) {
        group.addTo(map);
      } else {
        group.remove();
      }
    }

    function setAllVisible(visible) {
      Object.keys(groups).forEach(function (key) {
        setLayerVisible(key, visible);
      });
    }

    function resetView() {
      fitInitialBounds();
    }

    function invalidateSize() {
      window.setTimeout(function () {
        map.invalidateSize();
      }, 240);
    }

    fitInitialBounds();

    return {
      map: map,
      groups: groups,
      layerState: layerState,
      setLayerVisible: setLayerVisible,
      setAllVisible: setAllVisible,
      resetView: resetView,
      invalidateSize: invalidateSize
    };
  }

  App.MapController = {
    create: create
  };
})(window.CS2Zoning = window.CS2Zoning || {});
