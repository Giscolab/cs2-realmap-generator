(function (App) {
  "use strict";

  var WAIT_LIMIT = 80;
  var WAIT_DELAY = 75;

  function byId(id) {
    return document.getElementById(id);
  }

  function createOption(value, label, disabled) {
    var option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (disabled) {
      option.disabled = true;
    }
    return option;
  }

  function setStatus(context, text) {
    if (context.status) {
      context.status.textContent = text;
    }
  }

  function getWorldData() {
    var data = window.CS2ZoningWorld;
    if (!data || !Array.isArray(data.continents)) {
      return [];
    }
    return data.continents.filter(function (continent) {
      return continent && Array.isArray(continent.countries);
    });
  }

  function isValidPoint(point) {
    return Array.isArray(point) &&
      point.length >= 2 &&
      Number.isFinite(Number(point[0])) &&
      Number.isFinite(Number(point[1]));
  }

  function isValidBounds(bounds) {
    return Array.isArray(bounds) &&
      bounds.length >= 2 &&
      isValidPoint(bounds[0]) &&
      isValidPoint(bounds[1]);
  }

  function fitLocation(context, location, fallbackZoom) {
    if (!location || !context.map) {
      return;
    }

    if (context.map.stop) {
      context.map.stop();
    }

    if (isValidBounds(location.bbox)) {
      context.map.fitBounds(location.bbox, {
        padding: [28, 28],
        maxZoom: Number(location.zoom) || fallbackZoom,
        animate: false
      });
      return;
    }

    if (isValidPoint(location.center)) {
      context.map.setView(location.center, Number(location.zoom) || fallbackZoom, { animate: false });
    }
  }

  function focusCapital(context, capital) {
    if (!capital || !context.map) {
      return;
    }

    if (context.map.stop) {
      context.map.stop();
    }
    context.map.setView(
      [Number(capital.lat), Number(capital.lon)],
      Number(capital.zoom) || 11,
      { animate: false }
    );
  }

  function slugifyCountryCode(value) {
    var text = String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

    var aliases = {
      "tchequie": "cz",
      "czechia": "cz",
      "czech republic": "cz",
      "republique tcheque": "cz",
      "france": "fr",
      "germany": "de",
      "allemagne": "de",
      "italy": "it",
      "italie": "it",
      "spain": "es",
      "espagne": "es",
      "united states": "us",
      "etats unis": "us",
      "états unis": "us",
      "china": "cn",
      "chine": "cn",
      "japan": "jp",
      "japon": "jp",
      "united kingdom": "gb",
      "royaume uni": "gb"
    };

    if (aliases[text]) {
      return aliases[text];
    }

    return text
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 8) || "xx";
  }

  function notifyLocationSelected(context) {
    var country = getSelectedCountry(context);
    var capital = getSelectedCapital(context);

    window.dispatchEvent(new CustomEvent("cs2zoning:location-selected", {
      detail: {
        center: context.map.getCenter(),
        country: country ? country.name : "",
        countryCode: country ? slugifyCountryCode(country.code || country.iso2 || country.name) : "",
        city: capital ? capital.name : ""
      }
    }));
  }

  function replaceOptions(select, placeholder, options) {
    var nodes = [createOption("", placeholder, true)];
    options.forEach(function (option) {
      nodes.push(createOption(option.value, option.label, false));
    });
    select.replaceChildren.apply(select, nodes);
    select.value = "";
  }

  function setEnabled(select, enabled) {
    select.disabled = !enabled;
  }

  function getSelectedContinent(context) {
    var index = Number(context.continentSelect.value);
    return Number.isInteger(index) ? context.continents[index] : null;
  }

  function getSelectedCountry(context) {
    var continent = getSelectedContinent(context);
    var index = Number(context.countrySelect.value);
    if (!continent || !Number.isInteger(index)) {
      return null;
    }
    return continent.countries[index] || null;
  }

  function getSelectedCapital(context) {
    var country = getSelectedCountry(context);
    if (!country || context.capitalSelect.value !== "0") {
      return null;
    }
    return country.capital || null;
  }

  function fillContinents(context) {
    replaceOptions(
      context.continentSelect,
      "Choisir un continent",
      context.continents.map(function (continent, index) {
        return { value: String(index), label: continent.name };
      })
    );
  }

  function fillCountries(context, continent) {
    var countries = continent.countries.map(function (item, index) {
      return { value: String(index), label: item.name };
    });

    replaceOptions(context.countrySelect, "Choisir un pays", countries);
    replaceOptions(context.capitalSelect, "Choisir une capitale", []);
    setEnabled(context.countrySelect, countries.length > 0);
    setEnabled(context.capitalSelect, false);
    context.goButton.disabled = true;
  }

  function fillCapital(context, country) {
    var capital = country.capital;
    var options = capital ? [{ value: "0", label: capital.name }] : [];

    replaceOptions(context.capitalSelect, "Choisir une capitale", options);
    setEnabled(context.capitalSelect, options.length > 0);
    context.goButton.disabled = true;
  }

  function handleContinentChange(context) {
    var continent = getSelectedContinent(context);
    if (!continent) {
      setEnabled(context.countrySelect, false);
      setEnabled(context.capitalSelect, false);
      context.goButton.disabled = true;
      setStatus(context, "Sélectionnez une zone");
      return;
    }

    fillCountries(context, continent);
    fitLocation(context, continent, 3);
    notifyLocationSelected(context);
    setStatus(context, continent.name);
  }

  function handleCountryChange(context) {
    var country = getSelectedCountry(context);
    if (!country) {
      setEnabled(context.capitalSelect, false);
      context.goButton.disabled = true;
      setStatus(context, "Sélectionnez un pays");
      return;
    }

    fillCapital(context, country);
    fitLocation(context, country, 7);
    notifyLocationSelected(context);
    setStatus(context, country.name);
  }

  function handleCapitalChange(context) {
    var capital = getSelectedCapital(context);
    context.goButton.disabled = !capital;
    if (capital) {
      focusCapital(context, capital);
      notifyLocationSelected(context);
      setStatus(context, capital.name);
    }
  }

  function handleGo(context) {
    var capital = getSelectedCapital(context);
    if (capital) {
      focusCapital(context, capital);
      notifyLocationSelected(context);
      setStatus(context, capital.name);
    }
  }

  function bindEvents(context) {
    context.continentSelect.addEventListener("change", function () {
      handleContinentChange(context);
    });
    context.countrySelect.addEventListener("change", function () {
      handleCountryChange(context);
    });
    context.capitalSelect.addEventListener("change", function () {
      handleCapitalChange(context);
    });
    context.goButton.addEventListener("click", function () {
      handleGo(context);
    });
  }

  function create(mapController) {
    var context = {
      map: mapController.map,
      continents: getWorldData(),
      continentSelect: byId("location-continent"),
      countrySelect: byId("location-country"),
      capitalSelect: byId("location-capital"),
      goButton: byId("location-go"),
      status: byId("location-status")
    };

    if (!context.continentSelect || !context.countrySelect || !context.capitalSelect || !context.goButton) {
      return null;
    }

    if (!context.continents.length) {
      setStatus(context, "Données mondiales indisponibles");
      return null;
    }

    fillContinents(context);
    setEnabled(context.continentSelect, true);
    setEnabled(context.countrySelect, false);
    setEnabled(context.capitalSelect, false);
    context.goButton.disabled = true;
    bindEvents(context);
    setStatus(context, context.continents.length + " continents disponibles");

    return {
      context: context
    };
  }

  function waitForMap(attempt) {
    var state = App.state;
    if (state && state.mapController) {
      App.locationNavigator = create(state.mapController);
      return;
    }

    if (attempt < WAIT_LIMIT) {
      window.setTimeout(function () {
        waitForMap(attempt + 1);
      }, WAIT_DELAY);
      return;
    }

    var status = byId("location-status");
    if (status) {
      status.textContent = "Carte indisponible";
    }
  }

  function autoInit() {
    waitForMap(0);
  }

  App.LocationNavigator = {
    create: create,
    autoInit: autoInit
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoInit, { once: true });
  } else {
    autoInit();
  }
})(window.CS2Zoning = window.CS2Zoning || {});
