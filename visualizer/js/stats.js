(function (App) {
  "use strict";

  function sourceCount(dataset, key) {
    return dataset.sources[key] ? dataset.sources[key].count : 0;
  }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString("fr-FR");
  }

  function compute(dataset) {
    var residential = sourceCount(dataset, "residential");
    var commercial = sourceCount(dataset, "commercial") + sourceCount(dataset, "retail");
    var industrial = sourceCount(dataset, "industrial");
    var parking = sourceCount(dataset, "parking");
    var office = sourceCount(dataset, "office");
    var mixed = sourceCount(dataset, "mixed");
    var roads = sourceCount(dataset, "roads");
    var paths = sourceCount(dataset, "paths");
    var water = dataset.bundleTotals ? dataset.bundleTotals.water : 0;
    var railways = dataset.bundleTotals ? dataset.bundleTotals.railways : 0;
    var services = dataset.bundleTotals ? dataset.bundleTotals.services : 0;
    var visualEntities = Number.isFinite(dataset.totalVisualEntities)
      ? dataset.totalVisualEntities
      : dataset.totalRaw;

    return {
      total: visualEntities,
      residential: residential,
      commercial: commercial,
      industrial: industrial,
      parking: parking,
      office: office,
      mixed: mixed,
      roads: roads,
      paths: paths,
      water: water,
      railways: railways,
      services: services,
      cards: [
        { key: "total", label: "Entités visuelles", value: visualEntities },
        { key: "residential", label: "Résidentiel", value: residential },
        { key: "commercial", label: "Commercial", value: commercial },
        { key: "industrial", label: "Industrie", value: industrial },
        { key: "parking", label: "Stationnement", value: parking },
        { key: "office", label: "Bureaux", value: office },
        { key: "mixed", label: "Usage mixte", value: mixed },
        { key: "roads", label: "Routes", value: roads },
        { key: "paths", label: "Chemins", value: paths },
        { key: "water", label: "Hydrographie", value: water },
        { key: "railways", label: "Voies ferrées", value: railways },
        { key: "services", label: "Services", value: services }
      ]
    };
  }

  App.Stats = {
    compute: compute,
    formatNumber: formatNumber
  };
})(window.CS2Zoning = window.CS2Zoning || {});
