(function (App) {
  "use strict";

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

  function projectPath(map, latlngs) {
    return latlngs.map(function (latlng) {
      return map.latLngToContainerPoint(latlng);
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

  function exportPolylineLayer(map, layer, width, height, isPolygon) {
    var margin = 24;
    var style = pathStyle(layer, isPolygon);
    var elements = [];

    if (isPolygon) {
      var polygonGroups = [];

      collectPolygonGroups(layer.getLatLngs(), polygonGroups);
      polygonGroups.forEach(function (group) {
        var projectedRings = group.map(function (ring) {
          return projectPath(map, ring);
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
      var points = projectPath(map, latlngs);

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

  function exportCircleMarkerLayer(map, layer, width, height) {
    var latlng = layer.getLatLng && layer.getLatLng();
    var point = latlng ? map.latLngToContainerPoint(latlng) : null;
    var margin = 24;
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

  function collectVectorElements(map, size) {
    var elements = [];

    map.eachLayer(function (layer) {
      if (layer instanceof L.CircleMarker) {
        elements = elements.concat(exportCircleMarkerLayer(map, layer, size.x, size.y));
        return;
      }

      if (layer instanceof L.Polygon) {
        elements = elements.concat(exportPolylineLayer(map, layer, size.x, size.y, true));
        return;
      }

      if (layer instanceof L.Polyline) {
        elements = elements.concat(exportPolylineLayer(map, layer, size.x, size.y, false));
      }
    });

    return elements;
  }

  function buildSvg(map, elements) {
    var size = map.getSize();
    var center = map.getCenter();
    var bounds = map.getBounds();
    var metadata = {
      exportedAt: new Date().toISOString(),
      center: { lat: center.lat, lng: center.lng },
      zoom: map.getZoom(),
      bounds: {
        south: bounds.getSouth(),
        west: bounds.getWest(),
        north: bounds.getNorth(),
        east: bounds.getEast()
      },
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

  function downloadText(filename, text, mimeType) {
    var blob = new Blob([text], { type: mimeType });
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

  function filenamePrefix(packIndexPath) {
    var match = String(packIndexPath || "").match(/exports\/bundles\/([^/\\]+)\/geojson_pack/i);
    return match ? match[1] : "leaflet_overlay";
  }

  function flashButton(button, text) {
    var original = button.textContent;
    button.textContent = text;
    window.setTimeout(function () {
      button.textContent = original;
    }, 1200);
  }

  function exportOverlay(context) {
    var map = context.map;
    var size = map.getSize();
    var elements = collectVectorElements(map, size);

    if (!elements.length) {
      flashButton(context.button, "Aucun overlay");
      return;
    }

    var filename = filenamePrefix(context.packIndexPath) + "_leaflet_overlay.svg";
    downloadText(filename, buildSvg(map, elements), "image/svg+xml;charset=utf-8");
    flashButton(context.button, "SVG exporté");
  }

  function create(options) {
    var button = byId("export-overlay-svg");
    var map = options && options.map;

    if (!button || !map || typeof L === "undefined") {
      return null;
    }

    var context = {
      button: button,
      map: map,
      packIndexPath: options.packIndexPath || ""
    };

    button.addEventListener("click", function () {
      exportOverlay(context);
    });

    return {
      exportSvg: function () {
        exportOverlay(context);
      }
    };
  }

  App.OverlayExporter = {
    create: create
  };
})(window.CS2Zoning = window.CS2Zoning || {});
