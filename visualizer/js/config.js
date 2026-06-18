(function (App) {
  "use strict";

  App.Config = {
    fallbackBounds: [[33.409332, -118.077270], [33.924460, -117.458331]],
    fallbackCenter: [33.653495, -117.723999],
    fallbackZoom: 11,
    tileLayer: {
      url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      options: {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CartoDB</a>',
        subdomains: "abcd",
        maxZoom: 20
      }
    },
    dataSources: [
      { key: "residential", globalName: "DATA_RESIDENTIAL", label: "Résidentiel" },
      { key: "commercial", globalName: "DATA_COMMERCIAL", label: "Commercial" },
      { key: "retail", globalName: "DATA_RETAIL", label: "Commerce de détail" },
      { key: "industrial", globalName: "DATA_INDUSTRIAL", label: "Industrie" },
      { key: "parking", globalName: "DATA_PARKING", label: "Stationnement" },
      { key: "office", globalName: "DATA_OFFICE", label: "Bureaux" },
      { key: "mixed", globalName: "DATA_MIXED", label: "Usage mixte" },
      { key: "roads", globalName: "DATA_ROADS", label: "Routes" },
      { key: "paths", globalName: "DATA_PATHS", label: "Chemins/piéton" },
      { key: "water_lines_clipped", globalName: "DATA_WATER_LINES", label: "Eau — lignes" },
      { key: "water_areas_clipped", globalName: "DATA_WATER_AREAS", label: "Eau — surfaces" }
    ],
    layers: [
      {
        key: "res_high",
        source: "residential",
        zone: "high",
        category: "residential",
        label: "Résidentiel haute densité",
        description: "Immeubles, grands collectifs et quartiers denses",
        color: "#0b6f3a",
        stroke: "#064725",
        cs2: "Résidentiel haute densité",
        realWorld: "Grand immeuble résidentiel"
      },
      {
        key: "res_med",
        source: "residential",
        zone: "medium",
        category: "residential",
        label: "Résidentiel moyenne densité",
        description: "Maisons de ville et petits collectifs",
        color: "#2d9d54",
        stroke: "#176a35",
        cs2: "Résidentiel moyenne densité",
        realWorld: "Maisons de ville / petits collectifs"
      },
      {
        key: "res_low",
        source: "residential",
        zone: "low",
        category: "residential",
        label: "Résidentiel basse densité",
        description: "Habitat individuel et zones peu denses",
        color: "#7ab64d",
        stroke: "#4f7f31",
        cs2: "Résidentiel basse densité",
        realWorld: "Habitat individuel ou peu dense"
      },
      {
        key: "com_high",
        source: "commercial",
        zone: "high",
        category: "commercial",
        label: "Commercial haute densité",
        description: "Bureaux denses, centres commerciaux et grands volumes",
        color: "#1f57d6",
        stroke: "#123587",
        cs2: "Commercial haute densité",
        realWorld: "Bureaux denses / centre commercial"
      },
      {
        key: "com_low",
        source: "commercial",
        zone: "low",
        category: "commercial",
        label: "Commercial basse densité",
        description: "Commerces de proximité et petits bâtiments",
        color: "#4aa3ff",
        stroke: "#1f6fb8",
        cs2: "Commercial basse densité",
        realWorld: "Commerce de proximité"
      },
      {
        key: "retail",
        source: "retail",
        category: "commercial",
        label: "Commerce de détail",
        description: "Zones commerciales et landuse:retail",
        color: "#74c5ff",
        stroke: "#4188bd",
        cs2: "Commercial basse densité",
        realWorld: "Zone commerciale / commerce de détail"
      },
      {
        key: "industrial",
        source: "industrial",
        category: "industrial",
        label: "Industrie",
        description: "Usines, entrepôts et zones logistiques",
        color: "#d6ad32",
        stroke: "#8f6d14",
        cs2: "Industrie",
        realWorld: "Zone industrielle / entrepôt"
      },
      {
        key: "prk_ramp",
        source: "parking",
        zone: "ramp",
        category: "parking",
        label: "Parking en ouvrage",
        description: "Parkings à étages, couverts ou souterrains",
        color: "#5fe86e",
        stroke: "#28943a",
        cs2: "Parking en ouvrage",
        realWorld: "Parking à étages ou souterrain"
      },
      {
        key: "prk_surface",
        source: "parking",
        zone: "surface",
        category: "parking",
        label: "Parking de surface",
        description: "Stationnement au sol",
        color: "#b9ed70",
        stroke: "#799c3f",
        cs2: "Parking de surface",
        realWorld: "Stationnement au sol"
      },
      {
        key: "office",
        source: "office",
        category: "office",
        label: "Bureaux",
        description: "Tertiaire, administration et sièges d'entreprise",
        color: "#a46bd5",
        stroke: "#68448b",
        cs2: "Bureaux / administration",
        realWorld: "Immeuble de bureaux / administration"
      },
      {
        key: "mixed",
        source: "mixed",
        category: "mixed",
        label: "Usage mixte",
        description: "Commerces et logements dans un même secteur",
        color: "#2ed6e5",
        stroke: "#128894",
        cs2: "Usage mixte",
        realWorld: "Commerces + logements"
      },
      {
        key: "road_highway",
        source: "roads",
        roadCategory: "highway",
        category: "roads",
        geometry: "line",
        label: "Autoroute",
        description: "Motorways et trunks OSM",
        color: "#ff4d4d",
        stroke: "#ff4d4d",
        lineWeight: 4,
        cs2: "Routes",
        realWorld: "Autoroute / voie rapide"
      },
      {
        key: "road_large_road",
        source: "roads",
        roadCategory: "large_road",
        category: "roads",
        geometry: "line",
        label: "Axe principal",
        description: "Routes primary OSM",
        color: "#ff9f1c",
        stroke: "#ff9f1c",
        lineWeight: 3,
        cs2: "Routes",
        realWorld: "Axe principal OSM"
      },
      {
        key: "road_medium_road",
        source: "roads",
        roadCategory: "medium_road",
        category: "roads",
        geometry: "line",
        label: "Route secondaire",
        description: "Routes secondary OSM",
        color: "#ffd60a",
        stroke: "#ffd60a",
        lineWeight: 3,
        cs2: "Routes",
        realWorld: "Route secondaire OSM"
      },
      {
        key: "road_small_road",
        source: "roads",
        roadCategory: "small_road",
        category: "roads",
        geometry: "line",
        label: "Tertiaire / résidentielle",
        description: "Routes tertiary, residential et living_street",
        color: "#ffffff",
        stroke: "#ffffff",
        lineWeight: 2,
        cs2: "Routes",
        realWorld: "Route tertiaire ou résidentielle OSM"
      },
      {
        key: "road_ramp",
        source: "roads",
        roadCategory: "ramp",
        category: "roads",
        geometry: "line",
        label: "Bretelle / liaison",
        description: "Liens motorway/trunk/primary/secondary/tertiary",
        color: "#ff3df5",
        stroke: "#ff3df5",
        lineWeight: 3,
        cs2: "Routes",
        realWorld: "Bretelle routière OSM"
      },
      {
        key: "road_gravel_road",
        source: "roads",
        roadCategory: "gravel_road",
        category: "roads",
        geometry: "line",
        label: "Route non classée",
        description: "Routes unclassified, service, road, track et fallback",
        color: "#c7d0d9",
        stroke: "#c7d0d9",
        lineWeight: 1,
        cs2: "Routes",
        realWorld: "Route OSM non classée"
      },
      {
        key: "paths",
        source: "paths",
        roadCategory: "pathway",
        category: "paths",
        geometry: "line",
        label: "Chemins/piéton",
        description: "Footways, paths, steps et rues piétonnes",
        color: "#2ad4ff",
        stroke: "#2ad4ff",
        lineWeight: 1,
        cs2: "Chemins piétons",
        realWorld: "Chemin ou rue piétonne OSM"
      },
      {
        key: "water_lines",
        source: "water_lines_clipped",
        category: "water",
        geometry: "line",
        label: "Eau — lignes",
        description: "Rivières, canaux, drains, fossés et cours d’eau linéaires",
        color: "#38bdf8",
        stroke: "#38bdf8",
        lineWeight: 3,
        cs2: "Eau / cours d’eau",
        realWorld: "Cours d’eau linéaire OSM"
      },
      {
        key: "water_areas",
        source: "water_areas_clipped",
        category: "water",
        geometry: "polygon",
        label: "Eau — surfaces",
        description: "Lacs, bassins, réservoirs et surfaces natural=water",
        color: "#0ea5e9",
        stroke: "#0284c7",
        cs2: "Eau / surface",
        realWorld: "Surface d’eau OSM"
      }

    ]
  };
})(window.CS2Zoning = window.CS2Zoning || {});
