"""
classifiers.py

Logique de classification :
tags OpenStreetMap → catégories de zones Cities: Skylines II.

La classification reste volontairement simple :
OSM ne fournit pas toujours un vrai zonage urbain officiel.
On déduit donc une catégorie jouable CS2 à partir des tags disponibles.
"""


def parse_levels(value, default: int = 0) -> int:
    """
    Convertit building:levels / levels en entier robuste.

    Exemples acceptés :
    - "5"   -> 5
    - "3.5" -> 3
    - "3,5" -> 3
    - vide / invalide -> default
    """
    if value is None:
        return default

    text = str(value).strip().replace(",", ".")
    if not text:
        return default

    try:
        return int(float(text))
    except (ValueError, TypeError):
        return default


def classify_residential(tags: dict, building_levels_index: dict, element_id: int) -> str:
    """
    Classe une zone résidentielle en haute, moyenne ou basse densité.

    Logique adaptée aux villes nord-américaines et européennes :
    - haute densité : immeubles, appartements, 5 étages ou plus ;
    - moyenne densité : maisons de ville, dortoirs, 3 à 4 étages ;
    - basse densité : défaut quand aucune information de densité n’est fiable.
    """
    tag_levels = parse_levels(tags.get("building:levels") or tags.get("levels"), 0)
    idx_levels = building_levels_index.get(element_id, 0)
    effective_levels = max(tag_levels, idx_levels)

    residential_subtype = tags.get("residential", "").lower()
    building_type = tags.get("building", "").lower()

    if (
        effective_levels >= 5
        or residential_subtype in ("apartments", "apartment", "condominium", "condo")
        or building_type in ("apartments", "residential")
    ):
        return "high"

    if (
        effective_levels >= 3
        or building_type in ("terrace", "dormitory", "townhouse", "semidetached_house")
        or residential_subtype in ("townhouse", "dormitory", "semi", "terrace")
    ):
        return "medium"

    return "low"


def classify_commercial(tags: dict) -> str:
    """
    Classe une zone commerciale en haute ou basse densité.
    """
    levels = parse_levels(tags.get("building:levels") or tags.get("levels"), 1)
    building_type = tags.get("building", "").lower()
    shop = tags.get("shop", "").lower()
    office = tags.get("office", "").lower()

    if levels >= 4:
        return "high"

    if building_type in ("commercial", "retail", "office") and levels >= 3:
        return "high"

    if shop in ("mall", "department_store") or office:
        return "high"

    return "low"


def classify_parking(tags: dict) -> str:
    """
    Distingue parking en ouvrage et parking de surface.
    """
    parking_type = tags.get("parking", "").lower()
    building_type = tags.get("building", "").lower()

    if parking_type in ("multi-storey", "multistorey", "structure", "underground"):
        return "ramp"

    if building_type in ("parking", "garage", "garages"):
        return "ramp"

    return "surface"


def has_positive_tag(tags: dict, key: str) -> bool:
    """
    Vérifie qu'un tag OSM existe et n'exprime pas explicitement l'absence.
    """
    value = str(tags.get(key, "")).strip().lower()
    return value not in ("", "no", "false", "0", "none")


def classify_road(tags: dict) -> dict:
    """
    Classe un way routier OSM dans une grande famille lisible pour CS2.
    """
    highway = str(tags.get("highway", "")).strip().lower()
    junction = str(tags.get("junction", "")).strip().lower()

    if junction == "roundabout":
        return {
            "subcategory": "Roundabout",
            "sourceTag": "junction=roundabout",
            "confidence": "direct",
        }

    if has_positive_tag(tags, "bridge"):
        return {
            "subcategory": "Bridge",
            "sourceTag": f"bridge={tags.get('bridge')}",
            "confidence": "direct",
        }

    if has_positive_tag(tags, "tunnel"):
        return {
            "subcategory": "Tunnel",
            "sourceTag": f"tunnel={tags.get('tunnel')}",
            "confidence": "direct",
        }

    if highway in (
        "motorway_link",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
    ):
        return {
            "subcategory": "Highway Ramp",
            "sourceTag": f"highway={highway}",
            "confidence": "direct",
        }

    if highway in ("motorway", "trunk"):
        return {
            "subcategory": "Highway",
            "sourceTag": f"highway={highway}",
            "confidence": "direct",
        }

    if highway == "service":
        return {
            "subcategory": "Service Road",
            "sourceTag": "highway=service",
            "confidence": "direct",
        }

    if highway in (
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "living_street",
        "unclassified",
    ):
        return {
            "subcategory": "Road",
            "sourceTag": f"highway={highway}",
            "confidence": "direct",
        }

    return {
        "subcategory": "Unknown Road",
        "sourceTag": f"highway={highway}" if highway else "highway=*",
        "confidence": "unknown",
    }


def classify_path(tags: dict) -> dict:
    """
    Classe un way piéton extrait dans DATA_PATHS.
    """
    highway = str(tags.get("highway", "")).strip().lower()

    if highway == "pedestrian":
        return {
            "subcategory": "Pedestrian Street",
            "sourceTag": "highway=pedestrian",
            "confidence": "direct",
        }

    if highway == "footway":
        return {
            "subcategory": "Footway",
            "sourceTag": "highway=footway",
            "confidence": "direct",
        }

    if highway == "steps":
        return {
            "subcategory": "Steps",
            "sourceTag": "highway=steps",
            "confidence": "direct",
        }

    if highway == "path":
        return {
            "subcategory": "Path",
            "sourceTag": "highway=path",
            "confidence": "direct",
        }

    return {
        "subcategory": "Unknown Path",
        "sourceTag": f"highway={highway}" if highway else "highway=*",
        "confidence": "unknown",
    }
