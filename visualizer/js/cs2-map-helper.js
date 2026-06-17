(function (App) {
  "use strict";

  var BundleIdentity = App.CS2BundleIdentity;
  var CommandBuilder = App.CS2CommandBuilder;
  var HelperUi = App.CS2HelperUi;

  function getCityName(input) {
    var value = input && input.value ? String(input.value).trim() : "";
    return value;
  }

  function getInputValue(input, fallback) {
    var value = input && input.value ? String(input.value).trim() : "";
    return value || fallback;
  }

  function getCountryName(context) {
    return getInputValue(context.countryInput, BundleIdentity.defaults.country);
  }

  function resolveCountryCode(value, countryName) {
    if (!App.CountryCodes || !App.CountryCodes.resolve) {
      throw new Error("Référentiel de codes pays indisponible.");
    }

    return App.CountryCodes.resolve(value, countryName);
  }

  function getCountryCode(context) {
    var rawCode = getInputValue(context.countryCodeInput, "");
    var country = getCountryName(context);
    return resolveCountryCode(rawCode, country);
  }

  function getRecommendedWaterLevel(context) {
    var raw = getInputValue(context.waterLevelInput, CommandBuilder.defaultRecommendedWaterLevel);
    var value = Number(raw);

    return Number.isFinite(value) ? value : CommandBuilder.defaultRecommendedWaterLevel;
  }

  function getBundleMeta(context, state, cityName) {
    var centerLat = CommandBuilder.roundNumber(state.center.lat, 6);
    var centerLon = CommandBuilder.roundNumber(state.center.lng, 6);
    var country = getCountryName(context);
    var countryCode = getCountryCode(context);

    if (context.countryCodeInput && context.countryCodeInput.value !== countryCode) {
      context.countryCodeInput.value = countryCode;
    }

    var dynamicBundleId = BundleIdentity.sanitizeBundleId(
      BundleIdentity.buildDynamicBundleId(cityName, countryCode, centerLon, centerLat)
    );

    var loadedBundleId = "";
    var indexPath = context && context.packData ? String(context.packData.indexPath || "") : "";
    var match = indexPath.match(/(?:^|\/)exports\/bundles\/([^\/]+)\/geojson_pack\/reports\/layer_index\.json/i);

    if (match && match[1]) {
      loadedBundleId = BundleIdentity.sanitizeBundleId(decodeURIComponent(match[1]));
    }

    var isDefaultIrvine =
      BundleIdentity.slugifyBundlePart(cityName, "city") === BundleIdentity.slugifyBundlePart(BundleIdentity.defaults.city, "city") &&
      countryCode === BundleIdentity.defaults.countryCode &&
      Math.abs(centerLat - 33.653495) < 0.000001 &&
      Math.abs(centerLon - (-117.723999)) < 0.000001;

    var bundleId = loadedBundleId || (isDefaultIrvine ? BundleIdentity.defaults.bundleId : dynamicBundleId);
    var bundleDir = ".\\exports\\bundles\\" + bundleId;

    return {
      id: bundleId,
      city: cityName,
      country: country,
      countryCode: countryCode,
      recommendedCs2WaterLevel: getRecommendedWaterLevel(context),
      dir: bundleDir,
      pngDir: bundleDir + "\\png",
      geojsonDir: bundleDir + "\\geojson_pack"
    };
  }

  function syncBundleUi(context, bundleMeta) {
    if (context.bundleIdOutput && document.activeElement !== context.bundleIdOutput) {
      context.bundleIdOutput.value = bundleMeta.id;
    }
  }


  function dispatchTargetBundleUpdate(context, state, bundleMeta) {
    var rawCity = context.cityInput && context.cityInput.value
      ? String(context.cityInput.value).trim()
      : "";

    if (!rawCity || !bundleMeta || !bundleMeta.id) {
      window.dispatchEvent(new CustomEvent("cs2zoning:target-bundle-updated", {
        detail: {
          bundleId: "",
          label: "",
          city: "",
          country: "",
          countryCode: "",
          worldBBox: "",
          heightmapBBox: ""
        }
      }));
      return;
    }

    window.dispatchEvent(new CustomEvent("cs2zoning:target-bundle-updated", {
      detail: {
        bundleId: bundleMeta.id || "",
        label: bundleMeta.city && bundleMeta.country
          ? bundleMeta.city + ", " + bundleMeta.country
          : bundleMeta.id,
        city: bundleMeta.city || "",
        country: bundleMeta.country || "",
        countryCode: bundleMeta.countryCode || "",
        worldBBox: state.worldMapBBoxText || "",
        heightmapBBox: state.heightmapBBoxText || ""
      }
    }));
  }

  function syncInputs(context, state) {
    if (document.activeElement !== context.worldSizeInput) {
      context.worldSizeInput.value = CommandBuilder.formatNumber(state.worldMapSizeKm, 3);
    }
    if (document.activeElement !== context.heightmapSizeInput) {
      context.heightmapSizeInput.value = CommandBuilder.formatNumber(state.heightmapSizeKm, 3);
    }
    if (document.activeElement !== context.stepSelect) {
      context.stepSelect.value = String(state.stepMeters);
    }
  }


  function update(context, state) {
    var zoom = context.map.getZoom();
    var cityName = getCityName(context.cityInput);

    context.currentWorldBBox = state.worldMapBBoxText;
    context.currentHeightmapBBox = state.heightmapBBoxText;

    if (!cityName) {
      context.currentCommand = "";
      context.currentFullBundleCommand = "";

      syncInputs(context, state);

      if (context.bundleIdOutput && document.activeElement !== context.bundleIdOutput) {
        context.bundleIdOutput.value = "";
      }

      if (context.countryInput && document.activeElement !== context.countryInput) {
        context.countryInput.value = "";
      }

      if (context.countryCodeInput && document.activeElement !== context.countryCodeInput) {
        context.countryCodeInput.value = "";
      }

      context.currentWorldBBox = "";
      context.currentHeightmapBBox = "";

      dispatchTargetBundleUpdate(context, state, null);

      HelperUi.setText(context.latOutput, "-");
      HelperUi.setText(context.lonOutput, "-");
      HelperUi.setText(context.zoomOutput, "-");
      HelperUi.setText(context.worldBBoxOutput, "-");
      HelperUi.setText(context.heightmapBBoxOutput, "-");
      HelperUi.setText(context.commandOutput, "-");

      context.fullBundleCommandOutput = ensureFullBundleCommandUi(context);
      HelperUi.setText(context.fullBundleCommandOutput, "-");

      HelperUi.setText(context.status, "");
      return;
    }

    var bundleMeta = null;

    try {
      bundleMeta = getBundleMeta(context, state, cityName);
    } catch (error) {
      context.currentCommand = "";
      context.currentFullBundleCommand = "";

      syncInputs(context, state);
      dispatchTargetBundleUpdate(context, state, null);
      HelperUi.setText(context.latOutput, CommandBuilder.formatNumber(state.center.lat, 6));
      HelperUi.setText(context.lonOutput, CommandBuilder.formatNumber(state.center.lng, 6));
      HelperUi.setText(context.zoomOutput, CommandBuilder.formatNumber(zoom, 2));
      HelperUi.setText(context.worldBBoxOutput, state.worldMapBBoxText);
      HelperUi.setText(context.heightmapBBoxOutput, state.heightmapBBoxText);
      HelperUi.setText(context.commandOutput, "-");
      context.fullBundleCommandOutput = ensureFullBundleCommandUi(context);
      HelperUi.setText(context.fullBundleCommandOutput, "-");
      HelperUi.setText(context.status, error && error.message ? error.message : "Code pays inconnu.");
      return;
    }

    var command = CommandBuilder.buildCommand(cityName, state.heightmapBBoxText, bundleMeta);
    var fullBundleCommand = CommandBuilder.buildFullBundleCommand(state, bundleMeta);

    context.currentCommand = command;
    context.currentFullBundleCommand = fullBundleCommand;

    syncInputs(context, state);
    syncBundleUi(context, bundleMeta);
    dispatchTargetBundleUpdate(context, state, bundleMeta);
    HelperUi.setText(context.latOutput, CommandBuilder.formatNumber(state.center.lat, 6));
    HelperUi.setText(context.lonOutput, CommandBuilder.formatNumber(state.center.lng, 6));
    HelperUi.setText(context.zoomOutput, CommandBuilder.formatNumber(zoom, 2));
    HelperUi.setText(context.worldBBoxOutput, state.worldMapBBoxText);
    HelperUi.setText(context.heightmapBBoxOutput, state.heightmapBBoxText);
    HelperUi.setText(context.commandOutput, command);
    context.fullBundleCommandOutput = ensureFullBundleCommandUi(context);
    HelperUi.setText(context.fullBundleCommandOutput, fullBundleCommand);
    HelperUi.setText(context.status, "");
  }
  function ensureFullBundleCommandUi(context) {
    var existingOutput = HelperUi.byId("cs2-helper-bundle-command");

    if (existingOutput) {
      var existingCopyButton = HelperUi.byId("copy-cs2-bundle-command");

      if (existingCopyButton && existingCopyButton.getAttribute("data-cs2-bound") !== "true") {
        existingCopyButton.setAttribute("data-cs2-bound", "true");
        existingCopyButton.addEventListener("click", function () {
          HelperUi.copyText(context.currentFullBundleCommand || "", function () {
            HelperUi.flashButton(existingCopyButton, "Copié");
          });
        });
      }

      return existingOutput;
    }

    if (!context.commandOutput) {
      return null;
    }

    var commandBlock = context.commandOutput.parentElement;
    var container = commandBlock && commandBlock.parentElement;

    if (!commandBlock || !container) {
      return null;
    }

    var section = document.createElement("section");
    section.className = "cs2-helper-generated-section";
    section.style.borderTop = "1px solid rgba(255, 255, 255, 0.12)";
    section.style.marginTop = "12px";
    section.style.paddingTop = "12px";

    var title = document.createElement("h3");
    title.textContent = "Commande bundle complet";

    var actions = document.createElement("div");
    actions.className = "cs2-helper-actions";

    var copyButton = document.createElement("button");
    copyButton.id = "copy-cs2-bundle-command";
    copyButton.type = "button";
    copyButton.textContent = "Copier";

    var output = document.createElement("pre");
    output.id = "cs2-helper-bundle-command";
    output.className = "cs2-helper-output";
    output.textContent = "";

    actions.appendChild(copyButton);
    section.appendChild(title);
    section.appendChild(actions);
    section.appendChild(output);

    container.insertBefore(section, commandBlock.nextSibling);

    copyButton.addEventListener("click", function () {
      HelperUi.copyText(context.currentFullBundleCommand || "", function () {
        HelperUi.flashButton(copyButton, "Copié");
      });
    });

    return output;
  }

  function hydrateTargetFromDisplayedBundle(context) {
    if (!context || !context.packData) {
      return false;
    }

    var meta = BundleIdentity.parseDisplayedBundleMeta(context.packData);

    if (!meta) {
      return false;
    }

    if (context.cityInput) {
      context.cityInput.value = meta.city;
    }

    if (context.countryInput) {
      context.countryInput.value = meta.country;
    }

    if (context.countryCodeInput) {
      context.countryCodeInput.value = meta.countryCode;
    }

    if (context.bundleIdOutput) {
      context.bundleIdOutput.value = meta.id;
    }

    if (context.overlayController) {
      context.overlayController.setCenter(meta.center);
    }

    console.info("[CS2 Helper] Emplacement courant hydraté depuis le bundle chargé:", meta);

    return true;
  }

  function updateFromController(context) {
    update(context, context.overlayController.getState());
  }

  function bindSizeInputs(context) {
    context.worldSizeInput.addEventListener("input", function () {
      context.overlayController.setWorldMapSizeKm(context.worldSizeInput.value);
    });

    context.heightmapSizeInput.addEventListener("input", function () {
      context.overlayController.setHeightmapSizeKm(context.heightmapSizeInput.value);
    });

    context.stepSelect.addEventListener("change", function () {
      context.overlayController.setStepMeters(context.stepSelect.value);
    });

    context.cityInput.addEventListener("input", function () {
      updateFromController(context);
    });

    context.countryInput.addEventListener("input", function () {
      updateFromController(context);
    });

    context.countryCodeInput.addEventListener("input", function () {
      updateFromController(context);
    });

    context.waterLevelInput.addEventListener("input", function () {
      updateFromController(context);
    });
  }

  function bindMoveButtons(context) {
    context.moveNorth.addEventListener("click", context.overlayController.moveNorth);
    context.moveSouth.addEventListener("click", context.overlayController.moveSouth);
    context.moveEast.addEventListener("click", context.overlayController.moveEast);
    context.moveWest.addEventListener("click", context.overlayController.moveWest);
    context.syncCenter.addEventListener("click", context.overlayController.syncWithMapCenter);
    context.fitOverlay.addEventListener("click", context.overlayController.centerViewOnOverlay);
  }

  function bindLocationEvents(context) {
    window.addEventListener("cs2zoning:location-selected", function (event) {
      var detail = event && event.detail ? event.detail : {};

      if (detail.city && context.cityInput) {
        context.cityInput.value = detail.city;
      }

      if (detail.country && context.countryInput) {
        context.countryInput.value = detail.country;
      }

      if (detail.countryCode && context.countryCodeInput) {
        context.countryCodeInput.value = detail.countryCode;
      }

      updateFromController(context);
    });
  }


  function bindCopyButtons(context) {
    context.copyWorldBBox.addEventListener("click", function () {
      HelperUi.copyText(context.currentWorldBBox, function () {
        HelperUi.flashButton(context.copyWorldBBox, "Copié");
      });
    });

    context.copyHeightmapBBox.addEventListener("click", function () {
      HelperUi.copyText(context.currentHeightmapBBox, function () {
        HelperUi.flashButton(context.copyHeightmapBBox, "Copié");
      });
    });

    context.copyCommand.addEventListener("click", function () {
      HelperUi.copyText(context.currentCommand, function () {
        HelperUi.flashButton(context.copyCommand, "Copié");
      });
    });
  }
  function bind(context) {
    context.overlayController.onChange(function (state) {
      update(context, state);
    });

    context.map.on("zoomend", function () {
      updateFromController(context);
    });

    bindSizeInputs(context);
    bindMoveButtons(context);
    bindLocationEvents(context);
    bindCopyButtons(context);
  }

  function create(options) {
    var mapController = options && options.mapController;
    var overlayController = options && options.overlayController;
    var context = {
      map: mapController && mapController.map,
      overlayController: overlayController,
      status: HelperUi.byId("cs2-helper-status"),
      packData: options.packData || null,
      cityInput: HelperUi.byId("cs2-helper-city"),
      countryInput: HelperUi.byId("cs2-helper-country"),
      countryCodeInput: HelperUi.byId("cs2-helper-country-code"),
      waterLevelInput: HelperUi.byId("cs2-helper-water-level"),
      bundleIdOutput: HelperUi.byId("cs2-helper-bundle-id"),
      worldSizeInput: HelperUi.byId("cs2-helper-size"),
      heightmapSizeInput: HelperUi.byId("cs2-helper-heightmap-size"),
      stepSelect: HelperUi.byId("cs2-helper-step"),
      latOutput: HelperUi.byId("cs2-helper-lat"),
      lonOutput: HelperUi.byId("cs2-helper-lon"),
      zoomOutput: HelperUi.byId("cs2-helper-zoom"),
      worldBBoxOutput: HelperUi.byId("cs2-helper-bbox"),
      heightmapBBoxOutput: HelperUi.byId("cs2-helper-heightmap-bbox"),
      commandOutput: HelperUi.byId("cs2-helper-command"),
      moveNorth: HelperUi.byId("cs2-move-north"),
      moveSouth: HelperUi.byId("cs2-move-south"),
      moveEast: HelperUi.byId("cs2-move-east"),
      moveWest: HelperUi.byId("cs2-move-west"),
      syncCenter: HelperUi.byId("sync-cs2-overlay"),
      fitOverlay: HelperUi.byId("fit-cs2-overlay"),
      copyWorldBBox: HelperUi.byId("copy-cs2-bbox"),
      copyHeightmapBBox: HelperUi.byId("copy-cs2-heightmap-bbox"),
      copyCommand: HelperUi.byId("copy-cs2-command"),
      currentWorldBBox: "",
      currentHeightmapBBox: "",
      currentCommand: ""
    };

    if (!context.map ||
      !context.overlayController ||
      !context.cityInput ||
      !context.countryInput ||
      !context.countryCodeInput ||
      !context.waterLevelInput ||
      !context.bundleIdOutput ||
      !context.worldSizeInput ||
      !context.heightmapSizeInput ||
      !context.stepSelect ||
      !context.worldBBoxOutput ||
      !context.heightmapBBoxOutput ||
      !context.commandOutput ||
      !context.moveNorth ||
      !context.moveSouth ||
      !context.moveEast ||
      !context.moveWest ||
      !context.syncCenter ||
      !context.fitOverlay ||
      !context.copyWorldBBox ||
      !context.copyHeightmapBBox ||
      !context.copyCommand) {
      return null;
    }

    bind(context);
    hydrateTargetFromDisplayedBundle(context);
    updateFromController(context);

    return {
      update: function () {
        updateFromController(context);
      }
    };
  }

  App.CS2MapHelper = {
    create: create
  };
})(window.CS2Zoning = window.CS2Zoning || {});
