(function (App) {
  "use strict";

  var BUNDLE_INDEX_PATH = "../exports/bundles/bundle_index.json";

  var state = {
    bundleIndex: null,
    displayedBundleId: null,
    selectedLocalBundleId: null,
    targetBundleId: null,
    targetLabel: null
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, text) {
    var element = byId(id);
    if (element) {
      element.textContent = text;
    }
  }

  function getBundlesFromIndex(index) {
    if (!index) {
      return [];
    }

    if (Array.isArray(index.bundles)) {
      return index.bundles;
    }

    if (Array.isArray(index.items)) {
      return index.items;
    }

    if (Array.isArray(index.entries)) {
      return index.entries;
    }

    return [];
  }

  function getBundleId(bundle) {
    return String(bundle.id || bundle.bundleId || bundle.name || "").trim();
  }

  function getBundleLabel(bundle) {
    return (
      bundle.label ||
      bundle.displayName ||
      bundle.name ||
      bundle.city ||
      getBundleId(bundle)
    );
  }

  function normalizeSlashes(value) {
    return String(value || "").replace(/\\/g, "/");
  }

  function ensureRelativeFromVisualizer(path) {
    var normalized = normalizeSlashes(path).replace(/^\.?\//, "");

    if (normalized.indexOf("../") === 0) {
      return normalized;
    }

    if (normalized.indexOf("exports/") === 0) {
      return "../" + normalized;
    }

    return normalized;
  }

  function getBundleBasePath(bundle) {
    var id = getBundleId(bundle);

    var raw =
      bundle.visualizerPath ||
      bundle.webPath ||
      bundle.path ||
      bundle.directory ||
      "";

    if (raw) {
      raw = ensureRelativeFromVisualizer(raw);
      raw = raw.replace(/\/$/, "");

      if (/\/geojson_pack$/i.test(raw)) {
        raw = raw.replace(/\/geojson_pack$/i, "");
      }

      return raw;
    }

    return "../exports/bundles/" + encodeURIComponent(id);
  }

  function getBundleIndexPath(bundle) {
    var direct =
      bundle.packIndexPath ||
      bundle.layerIndexPath ||
      bundle.layer_index ||
      bundle.layerIndex ||
      "";

    if (direct) {
      return ensureRelativeFromVisualizer(direct);
    }

    return getBundleBasePath(bundle) + "/geojson_pack/reports/layer_index.json";
  }

  function getDisplayedPackIndexPathFromUrl() {
    try {
      var params = new URLSearchParams(window.location.search || "");
      return params.get("packIndexPath") || "";
    } catch (error) {
      return "";
    }
  }

  function getDisplayedBundleIdFromUrl() {
    var indexPath = getDisplayedPackIndexPathFromUrl();
    var match = normalizeSlashes(indexPath).match(/exports\/bundles\/([^/]+)\/geojson_pack\/reports\/layer_index\.json/i);

    if (!match) {
      return null;
    }

    return decodeURIComponent(match[1]);
  }

  function findBundleById(bundleId) {
    var bundles = getBundlesFromIndex(state.bundleIndex);

    for (var i = 0; i < bundles.length; i += 1) {
      if (getBundleId(bundles[i]) === bundleId) {
        return bundles[i];
      }
    }

    return null;
  }

  function renderDisplayedStatus() {
    state.displayedBundleId = getDisplayedBundleIdFromUrl();

    if (!state.displayedBundleId) {
      setText("displayed-bundle-status", "Pack affiché actuellement : aucun");
      return;
    }

    var bundle = findBundleById(state.displayedBundleId);
    var label = bundle ? getBundleLabel(bundle) : state.displayedBundleId;

    setText(
      "displayed-bundle-status",
      "Pack affiché actuellement : " + label + " — " + state.displayedBundleId
    );
  }



  function parseBundleIdParts(bundleId) {
    var match = String(bundleId || "").match(/^(.+)_([a-z]{2})_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)$/i);

    if (!match) {
      return null;
    }

    return {
      citySlug: match[1],
      countryCode: match[2].toLowerCase(),
      lat: Number(match[3]),
      lon: Number(match[4])
    };
  }

  function distanceKm(a, b) {
    if (!a || !b) {
      return Infinity;
    }

    if (!Number.isFinite(a.lat) || !Number.isFinite(a.lon) || !Number.isFinite(b.lat) || !Number.isFinite(b.lon)) {
      return Infinity;
    }

    var earthRadiusKm = 6371;
    var dLat = (b.lat - a.lat) * Math.PI / 180;
    var dLon = (b.lon - a.lon) * Math.PI / 180;
    var lat1 = a.lat * Math.PI / 180;
    var lat2 = b.lat * Math.PI / 180;

    var h =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1) * Math.cos(lat2) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);

    return 2 * earthRadiusKm * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  }

  function findBundleForTarget(bundleId) {
    var exact = findBundleById(bundleId);

    if (exact) {
      return exact;
    }

    var target = parseBundleIdParts(bundleId);

    if (!target) {
      return null;
    }

    var bundles = getBundlesFromIndex(state.bundleIndex);
    var best = null;
    var bestDistanceKm = Infinity;

    bundles.forEach(function (bundle) {
      var candidateId = getBundleId(bundle);
      var candidate = parseBundleIdParts(candidateId);

      if (!candidate) {
        return;
      }

      if (candidate.citySlug !== target.citySlug || candidate.countryCode !== target.countryCode) {
        return;
      }

      var d = distanceKm(target, candidate);

      if (d < bestDistanceKm) {
        best = bundle;
        bestDistanceKm = d;
      }
    });

    // Tolérance volontairement faible : corrige les arrondis type Paris 48.857000 vs 48.857487,
    // mais évite de confondre deux bundles différents dans la même grande ville.
    if (best && bestDistanceKm <= 1.0) {
      return best;
    }

    return null;
  }

  function renderTargetStatus() {
    var button = byId("load-target-bundle");

    if (!state.targetBundleId) {
      setText("target-bundle-status", "Zone cible sélectionnée : aucune");

      if (button) {
        button.disabled = true;
      }

      return;
    }

    var bundle = findBundleForTarget(state.targetBundleId);
    var label = state.targetLabel || state.targetBundleId;

    if (bundle) {
      setText(
        "target-bundle-status",
        "Zone cible sélectionnée : " + label + " — bundle local disponible"
      );

      if (button) {
        button.disabled = false;
      }

      return;
    }

    setText(
      "target-bundle-status",
      "Zone cible sélectionnée : " + label + " — bundle absent, génération requise"
    );

    if (button) {
      button.disabled = true;
    }
  }

  function loadTargetBundle() {
    if (!state.targetBundleId) {
      renderCatalogStatus("Aucun bundle cible.");
      return;
    }

    var bundle = findBundleForTarget(state.targetBundleId);

    if (!bundle) {
      renderCatalogStatus("Bundle cible absent localement : " + state.targetBundleId);
      renderTargetStatus();
      return;
    }

    state.selectedLocalBundleId = getBundleId(bundle);
    loadSelectedBundle();
  }

  function renderCatalogStatus(message) {
    setText("local-bundle-catalog-status", message);
  }

  function populateBundleSelect() {
    var select = byId("local-bundle-select");
    if (!select) {
      return;
    }

    select.innerHTML = "";

    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "-- sélectionner un bundle --";
    select.appendChild(empty);

    var bundles = getBundlesFromIndex(state.bundleIndex);

    bundles.forEach(function (bundle) {
      var id = getBundleId(bundle);
      if (!id) {
        return;
      }

      var option = document.createElement("option");
      option.value = id;
      option.textContent = getBundleLabel(bundle) + " — " + id;
      select.appendChild(option);
    });

    if (state.displayedBundleId) {
      select.value = state.displayedBundleId;
      state.selectedLocalBundleId = state.displayedBundleId;
    }

    renderCatalogStatus("Catalogue local chargé : " + bundles.length + " bundle(s)");
  }

  async function refreshCatalog() {
    renderCatalogStatus("Chargement du catalogue local...");

    try {
      var response = await fetch(BUNDLE_INDEX_PATH, { cache: "no-store" });

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      state.bundleIndex = await response.json();
      state.displayedBundleId = getDisplayedBundleIdFromUrl();

      populateBundleSelect();
      renderDisplayedStatus();
      renderTargetStatus();
    } catch (error) {
      console.warn("[BundleCatalog] Impossible de charger bundle_index.json", error);
      state.bundleIndex = null;
      populateBundleSelect();
      renderCatalogStatus("Catalogue local absent ou illisible : " + BUNDLE_INDEX_PATH);
      renderDisplayedStatus();
      renderTargetStatus();
    }
  }

  function loadSelectedBundle() {
    var bundleId = state.selectedLocalBundleId;

    if (!bundleId) {
      renderCatalogStatus("Aucun bundle sélectionné.");
      return;
    }

    var bundle = findBundleById(bundleId);

    if (!bundle) {
      renderCatalogStatus("Bundle introuvable dans le catalogue : " + bundleId);
      return;
    }

    var packIndexPath = getBundleIndexPath(bundle);
    var url = new URL(window.location.href);

    url.searchParams.set("packIndexPath", packIndexPath);

    window.location.href = url.toString();
  }

  function unloadDisplayedBundle() {
    var url = new URL(window.location.href);
    url.searchParams.delete("packIndexPath");
    window.location.href = url.pathname + url.search + url.hash;
  }

  function bindEvents() {
    var refreshButton = byId("refresh-bundle-catalog");
    if (refreshButton) {
      refreshButton.addEventListener("click", refreshCatalog);
    }

    var select = byId("local-bundle-select");
    if (select) {
      select.addEventListener("change", function () {
        state.selectedLocalBundleId = select.value || null;
      });
    }

    var loadButton = byId("load-selected-local-bundle");
    if (loadButton) {
      loadButton.addEventListener("click", loadSelectedBundle);
    }

    var unloadButton = byId("unload-displayed-bundle");
    if (unloadButton) {
      unloadButton.addEventListener("click", unloadDisplayedBundle);
    }

    var targetButton = byId("load-target-bundle");
    if (targetButton) {
      targetButton.addEventListener("click", loadTargetBundle);
    }

    window.addEventListener("cs2zoning:target-bundle-updated", function (event) {
      var detail = event.detail || {};

      state.targetBundleId = detail.bundleId || null;
      state.targetLabel = detail.label || detail.bundleId || null;

      renderTargetStatus();
    });

  }

  function init() {
    state.displayedBundleId = getDisplayedBundleIdFromUrl();
    bindEvents();
    renderDisplayedStatus();
    renderTargetStatus();
    refreshCatalog();
  }

  App.BundleCatalog = {
    init: init,
    refreshCatalog: refreshCatalog,
    state: state
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})(window.CS2Zoning = window.CS2Zoning || {});
