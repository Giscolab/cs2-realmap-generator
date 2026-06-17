(function (App) {
  "use strict";

  function showEmptyState(dataset) {
    var emptyState = document.getElementById("empty-state");

    if (emptyState) {
      emptyState.hidden = dataset.hasData;
    }
  }

  function hideLoading() {
    var loading = document.getElementById("app-loading");

    if (loading) {
      loading.classList.add("is-hidden");
    }
  }

  function showError(error) {
    var errorState = document.getElementById("app-error");
    var message = document.getElementById("app-error-message");

    if (message) {
      message.textContent = error && error.message ? error.message : "Erreur inconnue.";
    }

    if (errorState) {
      errorState.hidden = false;
    }
  }


  function isValidPackIndexPath(value) {
    // N'autorise qu'un layer_index.json sous ../exports/bundles/<bundleId>/...
    // et interdit toute remontée de chemin (.. au-delà du préfixe).
    var pattern = /^\.\.\/exports\/bundles\/[A-Za-z0-9._-]+\/geojson_pack\/reports\/layer_index\.json$/;
    return pattern.test(value) && value.indexOf("..", 1) === -1;
  }

  function getExplicitPackIndexPath() {
    try {
      var params = new URLSearchParams(window.location.search || "");
      var value = params.get("packIndexPath");

      if (!value) {
        return "";
      }

      var trimmed = value.trim();

      if (!isValidPackIndexPath(trimmed)) {
        console.warn("[Visualizer] packIndexPath refusé (attendu ../exports/bundles/<id>/geojson_pack/reports/layer_index.json) :", trimmed);
        return "";
      }

      return trimmed;
    } catch (error) {
      console.warn("[Visualizer] Impossible de lire packIndexPath dans l'URL.", error);
      return "";
    }
  }

  function loadPackOrFallback() {
    if (!App.PackLoader || !App.PackLoader.loadDefaultPack) {
      return Promise.resolve(null);
    }

    var explicitPackIndexPath = getExplicitPackIndexPath();

    if (explicitPackIndexPath) {
      var config = Object.assign({}, App.Config, {
        packIndexPath: explicitPackIndexPath
      });

      if (App.Status && App.Status.set) {
        App.Status.set("Chargement du bundle sélectionné");
      }

      return App.PackLoader.loadDefaultPack(config).catch(function (error) {
        console.warn("[CS2Zoning] Pack sélectionné introuvable ou illisible.", error);
        throw error;
      });
    }

    console.info("[Visualizer] Démarrage sans bundle chargé automatiquement.");
    if (App.Status && App.Status.set) {
      App.Status.set("Catalogue local uniquement — aucun bundle chargé");
    }
    return Promise.resolve(null);
  }

  function bootstrap() {
    loadPackOrFallback().then(function (packData) {
      var dataset = App.DataAdapter.createDataset(App.Config, packData);
      var stats = App.Stats.compute(dataset);

      var mapController = App.MapController.create({
        containerId: "map",
        config: App.Config,
        dataset: dataset
      });

      var overlayController = App.CS2OverlayController ? App.CS2OverlayController.create({
        map: mapController.map
      }) : null;

      var panel = App.PanelController.create({
        dataset: dataset,
        stats: stats,
        mapController: mapController
      });

      var cs2MapHelper = App.CS2MapHelper ? App.CS2MapHelper.create({
        mapController: mapController,
        overlayController: overlayController,
        packData: packData
      }) : null;

      panel.render();
      showEmptyState(dataset);
      hideLoading();

      App.state = {
        dataset: dataset,
        stats: stats,
        mapController: mapController,
        overlayController: overlayController,
        cs2MapHelper: cs2MapHelper,
        packData: packData
      };

      console.info(
        "[CS2Zoning] Données chargées en mode:",
        dataset.dataMode,
        dataset.packIndexPath || "aucun pack chargé"
      );
    }).catch(function (error) {
      console.error(error);
      showError(error);
      hideLoading();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap, { once: true });
  } else {
    bootstrap();
  }
})(window.CS2Zoning = window.CS2Zoning || {});
