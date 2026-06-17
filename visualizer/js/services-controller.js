(function (App) {
  "use strict";

  // Couleur par famille (markers). Valeurs sûres (constantes) injectées en style.
  var FAMILY_COLORS = {
    education: "#f4c453",
    fire: "#ff6978",
    medical: "#58d8ff",
    parks: "#56d68a",
    electricity: "#facc15",
    waste: "#9aa7b2",
    transport: "#2f9bff",
    water: "#38bdf8",
    communications: "#a46bd5"
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function formatCount(value) {
    return Number(value || 0).toLocaleString("fr-FR");
  }

  function familyColor(key) {
    return FAMILY_COLORS[key] || "#58d8ff";
  }

  function escape(value) {
    if (App.SafeHTML) {
      return App.SafeHTML.escapeHTML(value);
    }
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char];
    });
  }

  // Racine du pack à partir du chemin du layer_index (.../geojson_pack/reports/layer_index.json)
  function packRootFrom(indexPath) {
    if (!indexPath) {
      return "";
    }
    var marker = "/reports/";
    var i = String(indexPath).indexOf(marker);
    if (i >= 0) {
      return indexPath.slice(0, i + 1);
    }
    return String(indexPath).replace(/[^/]+$/, "");
  }

  function fetchJSON(path) {
    return fetch(path, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status + " — " + path);
      }
      return response.json();
    });
  }

  function serviceFilePath(family) {
    var key = String(family && family.key ? family.key : "service").replace(/[^A-Za-z0-9._-]/g, "");
    var fallback = "geojson/services/" + (key || "service") + ".geojson";
    var file = String(family && family.file ? family.file : fallback).replace(/\\/g, "/");

    if (/^geojson\/services\/[A-Za-z0-9._-]+\.geojson$/.test(file) && file.indexOf("..") === -1) {
      return file;
    }

    return fallback;
  }

  function buildMarkerGroup(geojson, family) {
    var group = L.layerGroup();
    var color = familyColor(family.key);
    var features = (geojson && geojson.features) || [];

    features.forEach(function (feature) {
      var geometry = feature && feature.geometry;
      if (!geometry || geometry.type !== "Point" || !Array.isArray(geometry.coordinates)) {
        return;
      }
      var lon = Number(geometry.coordinates[0]);
      var lat = Number(geometry.coordinates[1]);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return;
      }

      var props = feature.properties || {};
      var marker = L.circleMarker([lat, lon], {
        radius: 5,
        color: color,
        weight: 1,
        fillColor: color,
        fillOpacity: 0.85
      });

      marker.bindPopup(
        '<article class="cs2-popup">' +
        '<span class="popup-badge" style="--popup-color:' + color + ';">' + escape(family.label) + "</span>" +
        '<h3 class="popup-title">' + escape(props.name || "Service") + "</h3>" +
        '<p class="popup-line">' + escape(props.subcategoryLabel || props.subcategory || "") + "</p>" +
        "</article>"
      );
      group.addLayer(marker);
    });

    return group;
  }

  function setButtonState(button, state) {
    var labels = { idle: "Afficher", loading: "…", active: "Masquer", error: "Réessayer" };
    button.textContent = labels[state] || "Afficher";
    button.disabled = state === "loading";
    button.classList.toggle("is-active", state === "active");
    button.setAttribute("aria-pressed", state === "active" ? "true" : "false");
  }

  function toggleFamily(ctx, family, button) {
    var entry = ctx.layers[family.key] || (ctx.layers[family.key] = {});

    // Déjà chargée et affichée -> masquer
    if (entry.group && ctx.map.hasLayer(entry.group)) {
      ctx.map.removeLayer(entry.group);
      setButtonState(button, "idle");
      return;
    }
    // Déjà chargée mais masquée -> réafficher (pas de re-fetch)
    if (entry.group) {
      entry.group.addTo(ctx.map);
      setButtonState(button, "active");
      return;
    }
    // Première activation -> lazy-load
    if (entry.loading) {
      return;
    }
    entry.loading = true;
    setButtonState(button, "loading");

    var path = packRootFrom(ctx.packIndexPath) + serviceFilePath(family);
    fetchJSON(path).then(function (geojson) {
      entry.group = buildMarkerGroup(geojson, family);
      entry.group.addTo(ctx.map);
      entry.loading = false;
      setButtonState(button, "active");
    }).catch(function (error) {
      entry.loading = false;
      setButtonState(button, "error");
      console.warn("[Services] Chargement des points '" + family.key + "' échoué :", error);
    });
  }

  function familyCard(ctx, family) {
    var implemented = Boolean(family.implemented);
    var card = el("article", "service-card");
    if (!implemented) {
      card.classList.add("is-disabled");
    }

    var head = el("div", "service-head");
    head.append(el("span", "service-name", family.label || family.key));
    head.append(el(
      "span",
      "service-badge " + (implemented ? "is-on" : "is-off"),
      implemented ? "connecté" : "non connecté"
    ));
    head.append(el("span", "service-count", formatCount(family.count)));

    // Toggle de couche : seulement si implémentée, non vide, et carte dispo.
    var canToggle = implemented && Number(family.count) > 0 &&
      ctx.map && ctx.packIndexPath && typeof L !== "undefined";
    if (canToggle) {
      var toggle = el("button", "service-toggle", "Afficher");
      toggle.type = "button";
      toggle.setAttribute("aria-pressed", "false");
      toggle.setAttribute("aria-label", "Afficher les points " + (family.label || family.key));
      toggle.addEventListener("click", function () {
        toggleFamily(ctx, family, toggle);
      });
      head.append(toggle);
    }
    card.append(head);

    var subs = el("div", "service-subs");
    (family.subcategories || []).forEach(function (sub) {
      var row = el("div", "service-sub");
      row.append(el("span", "service-sub-label", sub.label || sub.key));
      row.append(el("span", "service-sub-count", formatCount(sub.count)));
      subs.append(row);
    });
    card.append(subs);

    return card;
  }

  function render(ctx) {
    var list = byId("services-list");
    var context = byId("services-context");
    if (!list) {
      return;
    }

    var servicesIndex = ctx.servicesIndex;
    if (!servicesIndex || !Array.isArray(servicesIndex.families)) {
      if (context) {
        context.textContent = "Aucun index — régénérez le bundle";
      }
      list.replaceChildren(
        el("p", "services-empty", "Index des services indisponible pour ce bundle.")
      );
      return;
    }

    var families = servicesIndex.families;
    if (context) {
      context.textContent = families.length + " familles";
    }
    list.replaceChildren.apply(list, families.map(function (family) {
      return familyCard(ctx, family);
    }));
  }

  App.ServicesController = {
    create: function (options) {
      var ctx = {
        servicesIndex: options && options.servicesIndex,
        map: options && options.map,
        packIndexPath: options && options.packIndexPath,
        layers: {}
      };
      return {
        render: function () {
          render(ctx);
        }
      };
    }
  };
})(window.CS2Zoning = window.CS2Zoning || {});
