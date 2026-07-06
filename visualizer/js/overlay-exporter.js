(function (App) {
  "use strict";

  var HEIGHTMAP_EXPORT_PIXELS = 4096;

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeXml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&apos;"
      }[char];
    });
  }

  function formatNumber(value) {
    return Number(value).toFixed(2).replace(/\.?0+$/, "");
  }

  function validColor(value, fallback) {
    var color = String(value || "").trim();
    return /^#[0-9a-fA-F]{3,8}$/.test(color) ? color : fallback;
  }

  function finitePoint(point) {
    return point && Number.isFinite(point.x) && Number.isFinite(point.y);
  }

  function isLatLng(value) {
    return value && Number.isFinite(Number(value.lat)) && Number.isFinite(Number(value.lng));
  }

  function collectLatLngPaths(value, output) {
    if (!Array.isArray(value) || !value.length) {
      return;
    }

    if (isLatLng(value[0])) {
      output.push(value);
      return;
    }

    value.forEach(function (item) {
      collectLatLngPaths(item, output);
    });
  }

  function collectPolygonGroups(value, output) {
    if (!Array.isArray(value) || !value.length) {
      return;
    }

    if (isLatLng(value[0])) {
      output.push([value]);
      return;
    }

    if (Array.isArray(value[0]) && value[0].length && isLatLng(value[0][0])) {
      output.push(value);
      return;
    }

    value.forEach(function (item) {
      collectPolygonGroups(item, output);
    });
  }

  function projectPath(projector, latlngs) {
    return latlngs.map(function (latlng) {
      return projector.project(latlng);
    }).filter(finitePoint);
  }

  function pathBounds(points) {
    return points.reduce(function (bounds, point) {
      bounds.minX = Math.min(bounds.minX, point.x);
      bounds.minY = Math.min(bounds.minY, point.y);
      bounds.maxX = Math.max(bounds.maxX, point.x);
      bounds.maxY = Math.max(bounds.maxY, point.y);
      return bounds;
    }, {
      minX: Infinity,
      minY: Infinity,
      maxX: -Infinity,
      maxY: -Infinity
    });
  }

  function intersectsViewport(bounds, width, height, margin) {
    return bounds.maxX >= -margin &&
      bounds.maxY >= -margin &&
      bounds.minX <= width + margin &&
      bounds.minY <= height + margin;
  }

  function svgPath(points, closePath) {
    if (!points.length) {
      return "";
    }

    var commands = ["M " + formatNumber(points[0].x) + " " + formatNumber(points[0].y)];
    points.slice(1).forEach(function (point) {
      commands.push("L " + formatNumber(point.x) + " " + formatNumber(point.y));
    });

    if (closePath) {
      commands.push("Z");
    }

    return commands.join(" ");
  }

  function pathStyle(layer, isPolygon) {
    var options = layer.options || {};
    var stroke = validColor(options.color, "#58d8ff");
    var fill = validColor(options.fillColor || options.color, stroke);
    var attrs = [
      'stroke="' + escapeXml(stroke) + '"',
      'stroke-width="' + escapeXml(options.weight == null ? 1 : options.weight) + '"',
      'stroke-opacity="' + escapeXml(options.opacity == null ? 1 : options.opacity) + '"',
      'stroke-linecap="' + escapeXml(options.lineCap || "round") + '"',
      'stroke-linejoin="' + escapeXml(options.lineJoin || "round") + '"'
    ];

    if (options.dashArray) {
      attrs.push('stroke-dasharray="' + escapeXml(options.dashArray) + '"');
    }

    if (isPolygon) {
      attrs.push('fill="' + escapeXml(fill) + '"');
      attrs.push('fill-opacity="' + escapeXml(options.fillOpacity == null ? 0.48 : options.fillOpacity) + '"');
      attrs.push('fill-rule="evenodd"');
    } else {
      attrs.push('fill="none"');
    }

    return attrs.join(" ");
  }

  function numericOption(value, fallback) {
    var number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function dashArray(value) {
    if (!value) {
      return [];
    }

    return String(value).split(/[,\s]+/).map(function (item) {
      return Number(item);
    }).filter(function (number) {
      return Number.isFinite(number) && number >= 0;
    });
  }

  function applyCanvasStyle(context, layer) {
    var options = layer.options || {};
    var stroke = validColor(options.color, "#58d8ff");

    context.lineWidth = numericOption(options.weight, 1);
    context.lineCap = options.lineCap || "round";
    context.lineJoin = options.lineJoin || "round";
    context.strokeStyle = stroke;
    context.setLineDash(dashArray(options.dashArray));
  }

  function traceCanvasPath(context, points, closePath) {
    if (!points.length) {
      return;
    }

    context.moveTo(points[0].x, points[0].y);
    points.slice(1).forEach(function (point) {
      context.lineTo(point.x, point.y);
    });

    if (closePath) {
      context.closePath();
    }
  }

  function drawCanvasPolylineLayer(context, projector, layer, isPolygon) {
    var margin = projector.margin == null ? 24 : projector.margin;
    var width = projector.width;
    var height = projector.height;
    var options = layer.options || {};
    var strokeOpacity = numericOption(options.opacity, 1);
    var drawn = 0;

    if (isPolygon) {
      var polygonGroups = [];

      collectPolygonGroups(layer.getLatLngs(), polygonGroups);
      polygonGroups.forEach(function (group) {
        var projectedRings = group.map(function (ring) {
          return projectPath(projector, ring);
        }).filter(function (points) {
          return points.length >= 3;
        });

        if (!projectedRings.length) {
          return;
        }

        var groupBounds = projectedRings.reduce(function (bounds, points) {
          var current = pathBounds(points);
          bounds.minX = Math.min(bounds.minX, current.minX);
          bounds.minY = Math.min(bounds.minY, current.minY);
          bounds.maxX = Math.max(bounds.maxX, current.maxX);
          bounds.maxY = Math.max(bounds.maxY, current.maxY);
          return bounds;
        }, {
          minX: Infinity,
          minY: Infinity,
          maxX: -Infinity,
          maxY: -Infinity
        });

        if (!intersectsViewport(groupBounds, width, height, margin)) {
          return;
        }

        context.save();
        applyCanvasStyle(context, layer);
        context.beginPath();
        projectedRings.forEach(function (points) {
          traceCanvasPath(context, points, true);
        });
        context.globalAlpha = numericOption(options.fillOpacity, 0.48);
        context.fillStyle = validColor(options.fillColor || options.color, validColor(options.color, "#58d8ff"));
        context.fill("evenodd");
        context.globalAlpha = strokeOpacity;
        context.stroke();
        context.restore();
        drawn += 1;
      });

      return drawn;
    }

    var latlngPaths = [];

    collectLatLngPaths(layer.getLatLngs(), latlngPaths);
    latlngPaths.forEach(function (latlngs) {
      var points = projectPath(projector, latlngs);

      if (points.length < 2 || !intersectsViewport(pathBounds(points), width, height, margin)) {
        return;
      }

      context.save();
      applyCanvasStyle(context, layer);
      context.beginPath();
      traceCanvasPath(context, points, false);
      context.globalAlpha = strokeOpacity;
      context.stroke();
      context.restore();
      drawn += 1;
    });

    return drawn;
  }

  function drawCanvasCircleMarkerLayer(context, projector, layer) {
    var latlng = layer.getLatLng && layer.getLatLng();
    var point = latlng ? projector.project(latlng) : null;
    var margin = projector.margin == null ? 24 : projector.margin;
    var width = projector.width;
    var height = projector.height;
    var options = layer.options || {};
    var radius = Number(layer._radius || options.radius || 5);
    var color = validColor(options.color, "#58d8ff");
    var fill = validColor(options.fillColor || options.color, color);

    if (!finitePoint(point) || !intersectsViewport({
      minX: point.x - radius,
      minY: point.y - radius,
      maxX: point.x + radius,
      maxY: point.y + radius
    }, width, height, margin)) {
      return 0;
    }

    context.save();
    context.beginPath();
    context.arc(point.x, point.y, radius, 0, Math.PI * 2);
    context.globalAlpha = numericOption(options.fillOpacity, 0.85);
    context.fillStyle = fill;
    context.fill();
    context.globalAlpha = numericOption(options.opacity, 1);
    context.lineWidth = numericOption(options.weight, 1);
    context.strokeStyle = color;
    context.stroke();
    context.restore();

    return 1;
  }

  function exportPolylineLayer(projector, layer, isPolygon) {
    var margin = projector.margin == null ? 24 : projector.margin;
    var width = projector.width;
    var height = projector.height;
    var style = pathStyle(layer, isPolygon);
    var elements = [];

    if (isPolygon) {
      var polygonGroups = [];

      collectPolygonGroups(layer.getLatLngs(), polygonGroups);
      polygonGroups.forEach(function (group) {
        var projectedRings = group.map(function (ring) {
          return projectPath(projector, ring);
        }).filter(function (points) {
          return points.length >= 3;
        });

        if (!projectedRings.length) {
          return;
        }

        var groupBounds = projectedRings.reduce(function (bounds, points) {
          var current = pathBounds(points);
          bounds.minX = Math.min(bounds.minX, current.minX);
          bounds.minY = Math.min(bounds.minY, current.minY);
          bounds.maxX = Math.max(bounds.maxX, current.maxX);
          bounds.maxY = Math.max(bounds.maxY, current.maxY);
          return bounds;
        }, {
          minX: Infinity,
          minY: Infinity,
          maxX: -Infinity,
          maxY: -Infinity
        });

        if (!intersectsViewport(groupBounds, width, height, margin)) {
          return;
        }

        elements.push('<path d="' + escapeXml(projectedRings.map(function (points) {
          return svgPath(points, true);
        }).join(" ")) + '" ' + style + ' />');
      });

      return elements;
    }

    var latlngPaths = [];

    collectLatLngPaths(layer.getLatLngs(), latlngPaths);
    latlngPaths.forEach(function (latlngs) {
      var points = projectPath(projector, latlngs);

      if (points.length < (isPolygon ? 3 : 2)) {
        return;
      }

      if (!intersectsViewport(pathBounds(points), width, height, margin)) {
        return;
      }

      elements.push('<path d="' + escapeXml(svgPath(points, isPolygon)) + '" ' + style + ' />');
    });

    return elements;
  }

  function exportCircleMarkerLayer(projector, layer) {
    var latlng = layer.getLatLng && layer.getLatLng();
    var point = latlng ? projector.project(latlng) : null;
    var margin = projector.margin == null ? 24 : projector.margin;
    var width = projector.width;
    var height = projector.height;
    var options = layer.options || {};
    var radius = Number(layer._radius || options.radius || 5);
    var color = validColor(options.color, "#58d8ff");
    var fill = validColor(options.fillColor || options.color, color);

    if (!finitePoint(point) || !intersectsViewport({
      minX: point.x - radius,
      minY: point.y - radius,
      maxX: point.x + radius,
      maxY: point.y + radius
    }, width, height, margin)) {
      return [];
    }

    return ['<circle cx="' + formatNumber(point.x) +
      '" cy="' + formatNumber(point.y) +
      '" r="' + formatNumber(radius) +
      '" stroke="' + escapeXml(color) +
      '" stroke-width="' + escapeXml(options.weight == null ? 1 : options.weight) +
      '" stroke-opacity="' + escapeXml(options.opacity == null ? 1 : options.opacity) +
      '" fill="' + escapeXml(fill) +
      '" fill-opacity="' + escapeXml(options.fillOpacity == null ? 0.85 : options.fillOpacity) +
      '" />'];
  }

  function shouldExportLayer(layer) {
    var options = layer.options || {};

    if (options.pane === "cs2-overlay-pane") {
      return false;
    }

    return true;
  }

  function collectVectorElements(map, projector) {
    var elements = [];

    map.eachLayer(function (layer) {
      if (!shouldExportLayer(layer)) {
        return;
      }

      if (layer instanceof L.CircleMarker) {
        elements = elements.concat(exportCircleMarkerLayer(projector, layer));
        return;
      }

      if (layer instanceof L.Polygon) {
        elements = elements.concat(exportPolylineLayer(projector, layer, true));
        return;
      }

      if (layer instanceof L.Polyline) {
        elements = elements.concat(exportPolylineLayer(projector, layer, false));
      }
    });

    return elements;
  }

  function drawCanvasOverlay(map, projector) {
    var canvas = document.createElement("canvas");
    var context = canvas.getContext("2d");
    var drawn = 0;

    canvas.width = projector.width;
    canvas.height = projector.height;
    context.clearRect(0, 0, canvas.width, canvas.height);

    map.eachLayer(function (layer) {
      if (!shouldExportLayer(layer)) {
        return;
      }

      if (layer instanceof L.CircleMarker) {
        drawn += drawCanvasCircleMarkerLayer(context, projector, layer);
        return;
      }

      if (layer instanceof L.Polygon) {
        drawn += drawCanvasPolylineLayer(context, projector, layer, true);
        return;
      }

      if (layer instanceof L.Polyline) {
        drawn += drawCanvasPolylineLayer(context, projector, layer, false);
      }
    });

    return {
      canvas: canvas,
      drawn: drawn
    };
  }

  function bboxFromLeafletBounds(bounds) {
    return {
      south: bounds.getSouth(),
      west: bounds.getWest(),
      north: bounds.getNorth(),
      east: bounds.getEast()
    };
  }

  function normalizeBBox(value) {
    if (!value) {
      return null;
    }

    var bbox = {
      south: Number(value.south),
      west: Number(value.west),
      north: Number(value.north),
      east: Number(value.east)
    };

    if (
      !Number.isFinite(bbox.south) ||
      !Number.isFinite(bbox.west) ||
      !Number.isFinite(bbox.north) ||
      !Number.isFinite(bbox.east) ||
      bbox.south >= bbox.north ||
      bbox.west >= bbox.east
    ) {
      return null;
    }

    return bbox;
  }

  function createViewportProjector(map) {
    var size = map.getSize();
    var center = map.getCenter();
    var bounds = map.getBounds();

    return {
      width: size.x,
      height: size.y,
      margin: 24,
      project: function (latlng) {
        return map.latLngToContainerPoint(latlng);
      },
      metadata: {
        mode: "leaflet-viewport",
        exportedAt: new Date().toISOString(),
        center: { lat: center.lat, lng: center.lng },
        zoom: map.getZoom(),
        bounds: bboxFromLeafletBounds(bounds)
      }
    };
  }

  function createBBoxProjector(map, bbox, pixels) {
    var normalized = normalizeBBox(bbox);
    var size = Number(pixels);
    var crs = map.options && map.options.crs ? map.options.crs : L.CRS.EPSG3857;
    var zoom = 0;
    var northWest;
    var southEast;

    if (!normalized || !Number.isFinite(size) || size <= 0) {
      return null;
    }

    northWest = crs.latLngToPoint(L.latLng(normalized.north, normalized.west), zoom);
    southEast = crs.latLngToPoint(L.latLng(normalized.south, normalized.east), zoom);

    if (
      !finitePoint(northWest) ||
      !finitePoint(southEast) ||
      northWest.x === southEast.x ||
      northWest.y === southEast.y
    ) {
      return null;
    }

    return {
      width: size,
      height: size,
      margin: 0,
      project: function (latlng) {
        var point = crs.latLngToPoint(latlng, zoom);

        return L.point(
          (point.x - northWest.x) / (southEast.x - northWest.x) * size,
          (point.y - northWest.y) / (southEast.y - northWest.y) * size
        );
      },
      metadata: {
        mode: "heightmap-bbox",
        exportedAt: new Date().toISOString(),
        pixels: size,
        bounds: normalized,
        projection: "Leaflet EPSG:3857"
      }
    };
  }

  function buildSvg(projector, elements) {
    var size = {
      x: projector.width,
      y: projector.height
    };
    var metadata = {
      export: projector.metadata || {},
      elementCount: elements.length
    };

    return [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + escapeXml(size.x) +
        '" height="' + escapeXml(size.y) +
        '" viewBox="0 0 ' + escapeXml(size.x) + " " + escapeXml(size.y) +
        '" fill="none">',
      '<metadata>' + escapeXml(JSON.stringify(metadata)) + "</metadata>",
      '<defs><clipPath id="viewport"><rect x="0" y="0" width="' + escapeXml(size.x) +
        '" height="' + escapeXml(size.y) + '" /></clipPath></defs>',
      '<g id="leaflet-overlay" clip-path="url(#viewport)">',
      elements.join("\n"),
      "</g>",
      "</svg>"
    ].join("\n");
  }

  function downloadBlob(filename, blob) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");

    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  function downloadText(filename, text, mimeType) {
    downloadBlob(filename, new Blob([text], { type: mimeType }));
  }

  function canvasToPngBlob(canvas) {
    return new Promise(function (resolve, reject) {
      canvas.toBlob(function (pngBlob) {
        if (pngBlob) {
          resolve(pngBlob);
          return;
        }
        reject(new Error("Impossible de générer le PNG."));
      }, "image/png");
    });
  }

  function filenamePrefix(packIndexPath) {
    var match = String(packIndexPath || "").match(/exports\/bundles\/([^/\\]+)\/geojson_pack/i);
    return match ? match[1] : "leaflet_overlay";
  }

  function flashButton(button, text) {
    if (!button) {
      return;
    }

    var original = button.dataset.overlayExporterOriginal || button.textContent;

    window.clearTimeout(Number(button.dataset.overlayExporterTimer || 0));
    button.dataset.overlayExporterOriginal = original;
    button.textContent = text;
    button.dataset.overlayExporterTimer = String(window.setTimeout(function () {
      button.textContent = original;
      delete button.dataset.overlayExporterOriginal;
      delete button.dataset.overlayExporterTimer;
    }, 1200));
  }

  function setButtonBusy(button, text) {
    if (!button) {
      return;
    }

    var original = button.dataset.overlayExporterOriginal || button.textContent;

    window.clearTimeout(Number(button.dataset.overlayExporterTimer || 0));
    button.dataset.overlayExporterOriginal = original;
    button.textContent = text;
  }

  function exportOverlay(context) {
    var map = context.map;
    var projector = createViewportProjector(map);
    var elements = collectVectorElements(map, projector);

    if (!elements.length) {
      flashButton(context.svgButton, "Aucun overlay");
      return;
    }

    var filename = filenamePrefix(context.packIndexPath) + "_leaflet_overlay.svg";
    downloadText(filename, buildSvg(projector, elements), "image/svg+xml;charset=utf-8");
    flashButton(context.svgButton, "SVG exporté");
  }

  function currentHeightmapBBox(context) {
    var state = context.overlayController && context.overlayController.getState
      ? context.overlayController.getState()
      : null;

    return normalizeBBox(state && state.heightmapBBox) ||
      bboxFromLeafletBounds(context.map.getBounds());
  }

  function exportOverlayPng(context) {
    var map = context.map;
    var bbox = currentHeightmapBBox(context);
    var projector = createBBoxProjector(map, bbox, HEIGHTMAP_EXPORT_PIXELS);
    var filename;

    if (!projector) {
      flashButton(context.pngButton, "BBOX invalide");
      return;
    }

    filename = filenamePrefix(context.packIndexPath) +
      "_leaflet_overlay_heightmap_" + HEIGHTMAP_EXPORT_PIXELS + ".png";

    setButtonBusy(context.pngButton, "PNG en cours");
    window.setTimeout(function () {
      var rendered = drawCanvasOverlay(map, projector);

      if (!rendered.drawn) {
        flashButton(context.pngButton, "Aucun overlay");
        return;
      }

      canvasToPngBlob(rendered.canvas).then(function (blob) {
        downloadBlob(filename, blob);
        flashButton(context.pngButton, "PNG exporté");
      }).catch(function (error) {
        console.error("[OverlayExporter] Export PNG impossible.", error);
        flashButton(context.pngButton, "Erreur PNG");
      });
    }, 0);
  }

  function create(options) {
    var svgButton = byId("export-overlay-svg");
    var pngButton = byId("export-overlay-png");
    var map = options && options.map;

    if ((!svgButton && !pngButton) || !map || typeof L === "undefined") {
      return null;
    }

    var context = {
      svgButton: svgButton,
      pngButton: pngButton,
      map: map,
      overlayController: options.overlayController || null,
      packIndexPath: options.packIndexPath || ""
    };

    if (svgButton) {
      svgButton.addEventListener("click", function () {
        exportOverlay(context);
      });
    }

    if (pngButton) {
      pngButton.addEventListener("click", function () {
        exportOverlayPng(context);
      });
    }

    return {
      exportSvg: function () {
        exportOverlay(context);
      },
      exportPng: function () {
        exportOverlayPng(context);
      }
    };
  }

  App.OverlayExporter = {
    create: create
  };
})(window.CS2Zoning = window.CS2Zoning || {});
