(function (App) {
  "use strict";

  var DEFAULTS = {
    bundleId: "irvine_ca_us_33.653495_-117.723999",
    city: "Irvine",
    country: "United States",
    countryCode: "us"
  };

  function stripAccents(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function slugifyBundlePart(value, fallback) {
    var slug = stripAccents(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");

    return slug || fallback;
  }

  function sanitizeBundleId(value) {
    var bundleId = stripAccents(value)
      .toLowerCase()
      .replace(/[^a-z0-9_.-]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");

    return bundleId || "bundle";
  }

  function buildDynamicBundleId(cityName, countryCode, centerLon, centerLat) {
    return [
      slugifyBundlePart(cityName, "city"),
      slugifyBundlePart(countryCode, "xx"),
      Number(centerLat).toFixed(6),
      Number(centerLon).toFixed(6)
    ].join("_");
  }

  function titleCaseBundleSlug(value) {
    return String(value || "")
      .split("_")
      .filter(Boolean)
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function getDisplayedBundleIdFromPackData(packData) {
    var indexPath = packData ? String(packData.indexPath || "") : "";
    var match = indexPath.match(/(?:^|\/)exports\/bundles\/([^\/]+)\/geojson_pack\/reports\/layer_index\.json/i);

    if (!match) {
      return "";
    }

    return sanitizeBundleId(decodeURIComponent(match[1]));
  }

  function parseDisplayedBundleMeta(packData) {
    var bundleId = getDisplayedBundleIdFromPackData(packData);
    var match = bundleId.match(/^(.+)_([a-z]{2})_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)$/i);

    if (!match) {
      return null;
    }

    var countryCode = match[2].toLowerCase();
    var lat = Number(match[3]);
    var lng = Number(match[4]);

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return null;
    }

    return {
      id: bundleId,
      city: titleCaseBundleSlug(match[1]),
      countryCode: countryCode,
      country: (App.CountryCodes && App.CountryCodes.namesByCode && App.CountryCodes.namesByCode[countryCode]) || countryCode.toUpperCase(),
      center: {
        lat: lat,
        lng: lng
      }
    };
  }

  App.CS2BundleIdentity = {
    defaults: DEFAULTS,
    slugifyBundlePart: slugifyBundlePart,
    sanitizeBundleId: sanitizeBundleId,
    buildDynamicBundleId: buildDynamicBundleId,
    parseDisplayedBundleMeta: parseDisplayedBundleMeta
  };
})(window.CS2Zoning = window.CS2Zoning || {});
