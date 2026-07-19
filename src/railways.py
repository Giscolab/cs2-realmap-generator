"""Extraction du réseau ferroviaire OSM en calque GeoJSON visuel.

Ce module décrit uniquement des géométries projetables. Il ne produit aucune
instruction d'import, aucun prefab, aucun spawner et aucune mutation du réseau
de transport de Cities: Skylines II.
"""

from __future__ import annotations


ACTIVE_RAILWAY_TYPES = (
    "rail",
    "narrow_gauge",
    "tram",
    "light_rail",
    "subway",
)

RAILWAY_SERVICE_TYPES = (
    "yard",
    "siding",
    "spur",
    "crossover",
)

_INACTIVE_LIFECYCLES = (
    "abandoned",
    "disused",
    "proposed",
    "construction",
)

_FALSE_OSM_VALUES = {"", "0", "false", "no", "none"}


def _clean_tag(value) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _normalized_tag(value) -> str:
    return (_clean_tag(value) or "").lower()


def _is_enabled_tag(value) -> bool:
    return _normalized_tag(value) not in _FALSE_OSM_VALUES


def build_railways_query(bbox: str) -> str:
    """Construit la requête Overpass des voies ferrées actives prises en charge.

    Seuls les ``way`` sont demandés afin que l'export final soit exclusivement
    composé de ``LineString``. Un second garde-fou côté client rejette les tags
    de cycle de vie inactifs parfois conservés sur une voie encore typée.
    """
    railway_values = "|".join(ACTIVE_RAILWAY_TYPES)
    return f"""
[out:json][timeout:180];
way["railway"~"^({railway_values})$"]({bbox});
out tags geom;
""".strip()


def is_active_railway(tags: dict | None) -> bool:
    """Indique si les tags représentent une voie active du périmètre V1."""
    if not isinstance(tags, dict):
        return False

    if _normalized_tag(tags.get("railway")) not in ACTIVE_RAILWAY_TYPES:
        return False

    for lifecycle in _INACTIVE_LIFECYCLES:
        if lifecycle in tags and _is_enabled_tag(tags.get(lifecycle)):
            return False

        for lifecycle_key in (f"{lifecycle}:railway", f"railway:{lifecycle}"):
            if lifecycle_key in tags and _is_enabled_tag(tags.get(lifecycle_key)):
                return False

    return True


def parse_osm_presence(value) -> bool:
    """Convertit un tag OSM de présence (yes, viaduct, culvert...) en booléen."""
    if value is None:
        return False
    return _is_enabled_tag(value)


def railway_properties(tags: dict) -> dict:
    """Retourne le contrat de propriétés stable de ``railways.geojson``.

    Les valeurs de service hors périmètre sont laissées à ``None`` : seules
    yard/siding/spur/crossover constituent la catégorie HUD « service » V1.
    """
    service = _normalized_tag(tags.get("service")) or None
    if service not in RAILWAY_SERVICE_TYPES:
        service = None

    return {
        "railway": _normalized_tag(tags.get("railway")),
        "usage": _clean_tag(tags.get("usage")),
        "service": service,
        "tracks": _clean_tag(tags.get("tracks")),
        "gauge": _clean_tag(tags.get("gauge")),
        "bridge": parse_osm_presence(tags.get("bridge")),
        "tunnel": parse_osm_presence(tags.get("tunnel")),
        "electrified": _clean_tag(tags.get("electrified")),
        "name": _clean_tag(tags.get("name")),
    }


def railway_item(element: dict) -> dict | None:
    """Convertit un élément Overpass en item linéaire, ou le rejette."""
    if element.get("type") != "way":
        return None

    tags = element.get("tags") or {}
    if not is_active_railway(tags):
        return None

    coords = []
    for point in element.get("geometry") or []:
        if point.get("lat") is None or point.get("lon") is None:
            continue
        coords.append([point["lat"], point["lon"]])

    if len(coords) < 2:
        return None

    return {
        "id": element.get("id"),
        **railway_properties(tags),
        "coords": coords,
    }
