"""
road_categories.py — Taxonomie unique des catégories routières CS2.

Source unique de vérité pour la classification couleur des routes, partagée
pipeline / visualizer / (à venir) CityTimelineMod. On garde ici des noms de base
neutres ; TimelineMod puis le jeu les renomment ensuite.

Correspondance OSM `highway` -> catégorie -> couleur :

    highway      Autoroute               rouge       motorway, trunk
    large_road   Axe principal           orange      primary
    medium_road  Route secondaire        jaune       secondary
    small_road   Tertiaire / résidentiel blanc       tertiary, residential, living_street
    ramp         Bretelle / liaison      magenta     *_link
    pathway      Chemin / piéton         cyan        pedestrian, footway, path, steps, cycleway, bridleway
    gravel_road  Route non classée       gris clair  unclassified, service, road, track + tout le reste

Les classes non listées explicitement par le contrat (residential, service…)
conservent leur rendu d'origine : residential/living_street en blanc (small_road),
service/unclassified/track en gris clair (gravel_road).
"""

from __future__ import annotations


ROAD_CATEGORIES: list[dict] = [
    {"key": "highway", "label": "Autoroute", "color": "#ff4d4d",
     "highways": ["motorway", "trunk"]},
    {"key": "large_road", "label": "Axe principal", "color": "#ff9f1c",
     "highways": ["primary"]},
    {"key": "medium_road", "label": "Route secondaire", "color": "#ffd60a",
     "highways": ["secondary"]},
    {"key": "small_road", "label": "Route tertiaire / résidentielle", "color": "#ffffff",
     "highways": ["tertiary", "residential", "living_street"]},
    {"key": "ramp", "label": "Bretelle / liaison", "color": "#ff3df5",
     "highways": ["motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"]},
    {"key": "pathway", "label": "Chemin / piéton", "color": "#2ad4ff",
     "highways": ["pedestrian", "footway", "path", "steps", "cycleway", "bridleway"]},
    {"key": "gravel_road", "label": "Route non classée", "color": "#c7d0d9",
     "highways": ["unclassified", "service", "road", "track"]},
]

# Catégorie par défaut pour une voie carrossable non reconnue (-> gris clair).
DEFAULT_ROAD_CATEGORY = "gravel_road"

_HIGHWAY_TO_CATEGORY = {
    highway: category["key"]
    for category in ROAD_CATEGORIES
    for highway in category["highways"]
}
_COLOR_BY_CATEGORY = {category["key"]: category["color"] for category in ROAD_CATEGORIES}
_LABEL_BY_CATEGORY = {category["key"]: category["label"] for category in ROAD_CATEGORIES}


def classify_road_category(tags: dict) -> str:
    """Renvoie la clé de catégorie routière depuis les tags OSM (fallback gravel_road)."""
    highway = str((tags or {}).get("highway", "")).strip().lower()
    return _HIGHWAY_TO_CATEGORY.get(highway, DEFAULT_ROAD_CATEGORY)


def road_category_color(category_key: str) -> str:
    return _COLOR_BY_CATEGORY.get(category_key, _COLOR_BY_CATEGORY[DEFAULT_ROAD_CATEGORY])


def road_category_label(category_key: str) -> str:
    return _LABEL_BY_CATEGORY.get(category_key, category_key)


def road_category_keys() -> list[str]:
    return [category["key"] for category in ROAD_CATEGORIES]
