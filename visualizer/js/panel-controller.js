(function (App) {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    var element = byId(id);
    if (element) {
      element.textContent = value;
    }
  }

  function createElement(tagName, className, text) {
    var element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    return element;
  }

  function createMetricCard(card) {
    var article = createElement("article", "metric-card");
    article.append(
      createElement("div", "metric-value", App.Stats.formatNumber(card.value)),
      createElement("div", "metric-label", card.label)
    );
    return article;
  }

  function createLayerButton(layerData) {
    var layer = layerData.definition;
    var button = createElement("button", "layer-toggle");
    var main = createElement("span", "layer-main");

    button.type = "button";
    button.setAttribute("role", "listitem");
    button.setAttribute("aria-pressed", "true");
    button.dataset.layerKey = layer.key;
    button.style.setProperty("--layer-color", layer.color);

    main.append(
      createElement("span", "layer-name", layer.label),
      createElement("span", "layer-description", layer.description)
    );

    button.append(
      createElement("span", "layer-swatch"),
      main,
      createElement("span", "layer-count", App.Stats.formatNumber(layerData.count))
    );

    button.querySelector(".layer-swatch").setAttribute("aria-hidden", "true");
    button.querySelector(".layer-count").setAttribute("aria-label", layerData.count + " objets");
    return button;
  }

  function createLegendItem(layer) {
    var item = createElement("div", "legend-item");
    var swatch = createElement("span", "legend-swatch");

    item.style.setProperty("--layer-color", layer.color);
    swatch.setAttribute("aria-hidden", "true");
    item.append(swatch, createElement("span", "", layer.label));
    return item;
  }

  function createLayerIndex(dataset) {
    return dataset.layers.reduce(function (index, layerData) {
      index[layerData.definition.key] = layerData;
      return index;
    }, {});
  }

  function updateVisibleCount(dataset) {
    var active = dataset.layers.filter(function (layerData) {
      return layerData.active;
    }).length;
    setText("visible-count", active + " active" + (active > 1 ? "s" : ""));
  }

  function updateButtonState(key, active) {
    var button = document.querySelector('[data-layer-key="' + key + '"]');
    if (button) {
      button.setAttribute("aria-pressed", active ? "true" : "false");
    }
  }

  function renderStatus(context) {
    var status = byId("dataset-status");
    var dataset = context.dataset;

    setText("dataset-status", dataset.hasData ? "Données chargées" : "Aucune donnée");
    setText(
      "dataset-substatus",
      dataset.hasData ? App.Stats.formatNumber(dataset.totalRaw) + " objets détectés" : "Pack GeoJSON absent ou vide"    );
    setText("metrics-context", dataset.hasRenderableData ? "Objets OSM exploitables" : "Mode attente de données");

    if (status) {
      status.classList.toggle("is-empty", !dataset.hasData);
    }
  }

  function renderMetrics(context) {
    if (context.metricsGrid) {
      context.metricsGrid.replaceChildren.apply(
        context.metricsGrid,
        context.stats.cards.map(createMetricCard)
      );
    }
  }

  function renderLayers(context) {
    if (context.layerList) {
      context.layerList.replaceChildren.apply(
        context.layerList,
        context.dataset.layers.map(createLayerButton)
      );
    }
    updateVisibleCount(context.dataset);
  }

  function renderLegend(context) {
    if (context.legendList) {
      context.legendList.replaceChildren.apply(
        context.legendList,
        context.dataset.layers.map(function (layerData) {
          return createLegendItem(layerData.definition);
        })
      );
    }
  }

  function setLayerActive(context, layerData, active) {
    layerData.active = active;
    context.mapController.setLayerVisible(layerData.definition.key, active);
    updateButtonState(layerData.definition.key, active);
  }

  function setAllLayers(context, active) {
    context.dataset.layers.forEach(function (layerData) {
      layerData.active = active;
      updateButtonState(layerData.definition.key, active);
    });
    context.mapController.setAllVisible(active);
    updateVisibleCount(context.dataset);
  }

  function bindLayerControls(context) {
    if (!context.layerList) {
      return;
    }
    context.layerList.addEventListener("click", function (event) {
      var button = event.target.closest("[data-layer-key]");
      var layerData = button ? context.layersByKey[button.dataset.layerKey] : null;

      if (!layerData) {
        return;
      }

      setLayerActive(context, layerData, !layerData.active);
      updateVisibleCount(context.dataset);
    });
  }

  function bindToolbar(context) {
    var showAll = byId("show-all-layers");
    var hideAll = byId("hide-all-layers");
    var resetView = byId("reset-view");

    if (showAll) {
      showAll.addEventListener("click", function () {
        setAllLayers(context, true);
      });
    }
    if (hideAll) {
      hideAll.addEventListener("click", function () {
        setAllLayers(context, false);
      });
    }
    if (resetView) {
      resetView.addEventListener("click", context.mapController.resetView);
    }
  }

  function bindPanelToggle(context) {
    if (!context.panelToggle) {
      return;
    }
    context.panelToggle.addEventListener("click", function () {
      var collapsed = document.body.classList.toggle("panel-collapsed");
      context.panelToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      context.mapController.invalidateSize();
    });
  }

  function render(context) {
    renderStatus(context);
    renderMetrics(context);
    renderLayers(context);
    renderLegend(context);
    bindLayerControls(context);
    bindToolbar(context);
    bindPanelToggle(context);
  }

  function create(options) {
    var context = {
      dataset: options.dataset,
      stats: options.stats,
      mapController: options.mapController,
      layersByKey: createLayerIndex(options.dataset),
      layerList: byId("layer-controls"),
      metricsGrid: byId("metrics-grid"),
      legendList: byId("legend-list"),
      panelToggle: byId("panel-toggle")
    };

    return {
      render: function () {
        render(context);
      }
    };
  }

  App.PanelController = {
    create: create
  };
})(window.CS2Zoning = window.CS2Zoning || {});
