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

  function loadPackOrFallback() {
    if (!App.PackLoader || !App.PackLoader.loadDefaultPack) {
      return Promise.resolve(null);
    }

    return App.PackLoader.loadDefaultPack(App.Config).catch(function (error) {
console.warn("[CS2Zoning] Pack exports introuvable ou illisible. Le visualiseur reste en attente de données.", error);
      return null;
    });
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


