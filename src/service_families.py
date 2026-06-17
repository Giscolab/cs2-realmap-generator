"""
service_families.py — Familles de services CS2 extraites d'OpenStreetMap.

Source unique de vérité pour les familles de services affichées par le HUD
CityTimelineMod (Éducation, Électricité, Pompiers, Déchets, Médical, Transports,
Eau/égouts, Communications, Parcs).

Les services OSM sont le plus souvent des *nœuds* (amenity=...), parfois des
surfaces (way/relation). On extrait donc UN POINT représentatif par élément :
- nœud  -> sa position (lat/lon) ;
- way/relation -> le `center` renvoyé par Overpass (`out center`).

État d'implémentation
---------------------
Chaque famille porte un drapeau `implemented`. Les 9 familles du HUD sont
connectées au pipeline ; certaines sous-catégories restent volontairement sans
sélecteur quand OSM ne les distingue pas de manière fiable.

La classification reste heuristique : OSM ne distingue pas toujours finement les
sous-catégories (ex. école primaire vs collège). On mappe ce qu'OSM fournit de
manière défendable ; les sous-catégories non mappables restent à 0.
"""

from __future__ import annotations


# Une "famille" = {key, label, implemented, subcategories[]}
# Une "sous-catégorie" = {key, label, selectors[]}
# Un "sélecteur" = {osm_key: [valeurs acceptées]}  (match si tags[osm_key] in valeurs)
SERVICE_FAMILIES: list[dict] = [
    {
        "key": "education",
        "label": "Éducation et recherche",
        "implemented": True,
        "subcategories": [
            {"key": "primary", "label": "École primaire",
             "selectors": [{"amenity": ["kindergarten", "school"]}]},
            # "Collège / lycée" : OSM ne distingue pas fiablement du primaire
            # (amenity=school couvre tout). Laissé vide volontairement.
            {"key": "secondary", "label": "Collège / lycée", "selectors": []},
            {"key": "university", "label": "Université",
             "selectors": [{"amenity": ["university", "college"]}]},
            {"key": "research", "label": "Recherche",
             "selectors": [{"amenity": ["research_institute"]}, {"office": ["research"]}]},
        ],
    },
    {
        "key": "fire",
        "label": "Sapeurs-pompiers",
        "implemented": True,
        "subcategories": [
            {"key": "local_station", "label": "Caserne locale",
             "selectors": [{"amenity": ["fire_station"]}]},
            {"key": "large_station", "label": "Grande caserne", "selectors": []},
            {"key": "special_rescue", "label": "Surveillance / secours spécialisés",
             "selectors": [{"emergency": ["water_rescue_station", "lifeguard_base", "lifeguard_tower"]}]},
        ],
    },
    {
        "key": "medical",
        "label": "Services médicaux et soins mortuaires",
        "implemented": True,
        "subcategories": [
            {"key": "clinic", "label": "Clinique",
             "selectors": [{"amenity": ["clinic", "doctors"]}]},
            {"key": "hospital", "label": "Hôpital",
             "selectors": [{"amenity": ["hospital"]}]},
            {"key": "crematorium", "label": "Crématorium",
             "selectors": [{"amenity": ["crematorium"]}]},
            {"key": "cemetery", "label": "Cimetière",
             "selectors": [{"amenity": ["grave_yard"]}, {"landuse": ["cemetery"]}]},
        ],
    },
    {
        "key": "parks",
        "label": "Parcs et loisirs",
        "implemented": True,
        "subcategories": [
            {"key": "local_park", "label": "Parc local",
             "selectors": [{"leisure": ["park", "garden"]}]},
            # "Grand parc" : nécessiterait la surface (non extraite ici). Laissé vide.
            {"key": "large_park", "label": "Grand parc",
             "selectors": [{"leisure": ["nature_reserve"]}]},
            {"key": "sport", "label": "Sport",
             "selectors": [{"leisure": ["sports_centre", "stadium", "pitch", "track"]}]},
            {"key": "leisure", "label": "Loisirs",
             "selectors": [{"leisure": ["playground", "recreation_ground", "water_park"]}]},
            {"key": "tourism", "label": "Tourisme",
             "selectors": [{"tourism": ["attraction", "museum", "zoo", "theme_park", "viewpoint"]}]},
        ],
    },

    {"key": "electricity", "label": "Électricité", "implemented": True, "subcategories": [
        {"key": "generation", "label": "Production électrique",
         "selectors": [{"power": ["plant", "generator"]}]},
        {"key": "transformation", "label": "Transformation",
         "selectors": [{"power": ["substation", "transformer"]}]},
        {"key": "storage", "label": "Stockage",
         "selectors": [{"power": ["storage"]}]},
        {"key": "grid", "label": "Réseau électrique",
         "selectors": [{"power": ["line", "minor_line", "cable", "tower", "pole", "portal"]}]},
    ]},
    {"key": "waste", "label": "Gestion des déchets", "implemented": True, "subcategories": [
        {"key": "collection", "label": "Collecte",
         "selectors": [{"amenity": ["waste_disposal", "waste_transfer_station"]}]},
        {"key": "recycling", "label": "Recyclage",
         "selectors": [{"amenity": ["recycling"]}]},
        {"key": "treatment", "label": "Traitement",
         "selectors": [{"man_made": ["incinerator", "wastewater_plant"]}]},
        {"key": "landfill", "label": "Décharge / stockage",
         "selectors": [{"landuse": ["landfill"]}]},
    ]},
    {"key": "transport", "label": "Transports", "implemented": True, "subcategories": [
        {"key": "bus", "label": "Bus",
         "selectors": [{"highway": ["bus_stop"]}, {"amenity": ["bus_station"]}]},
        {"key": "tram", "label": "Tram",
         "selectors": [{"railway": ["tram_stop"]}]},
        {"key": "train", "label": "Train",
         "selectors": [{"railway": ["station", "halt"]}]},
        {"key": "metro", "label": "Métro",
         "selectors": [{"railway": ["subway_entrance"]}, {"station": ["subway"]}]},
        {"key": "taxi", "label": "Taxi",
         "selectors": [{"amenity": ["taxi"]}]},
        {"key": "air", "label": "Aérien",
         "selectors": [{"aeroway": ["aerodrome", "terminal", "helipad"]}]},
        {"key": "maritime", "label": "Maritime",
         "selectors": [{"amenity": ["ferry_terminal"]}]},
    ]},
    {"key": "water", "label": "Eau et égouts", "implemented": True, "subcategories": [
        {"key": "pumping", "label": "Pompage",
         "selectors": [{"man_made": ["pump", "pumping_station", "water_tower", "water_well"]}]},
        {"key": "water_treatment", "label": "Traitement de l'eau",
         "selectors": [{"man_made": ["water_works"]}]},
        {"key": "sewage", "label": "Égouts",
         "selectors": [{"waterway": ["drain", "ditch"]}, {"man_made": ["sewer"]}]},
        {"key": "wastewater", "label": "Traitement des eaux usées",
         "selectors": [{"man_made": ["wastewater_plant"]}]},
    ]},
    {"key": "communications", "label": "Communications", "implemented": True, "subcategories": [
        {"key": "post", "label": "Poste",
         "selectors": [{"amenity": ["post_office"]}]},
        {"key": "telecom", "label": "Télécommunications",
         "selectors": [{"telecom": ["exchange", "service_device", "connection_point"]},
                       {"man_made": ["telephone_exchange", "telecommunication_tower"]}]},
        {"key": "datacenter", "label": "Serveurs / data center",
         "selectors": [{"building": ["data_center"]}, {"man_made": ["data_center"]}, {"telecom": ["data_center"]}]},
        {"key": "radio", "label": "Radio / antennes",
         "selectors": [{"man_made": ["antenna", "communications_tower", "mast"]},
                       {"tower:type": ["communication"]}]},
    ]},
]


def implemented_families() -> list[dict]:
    """Familles possédant au moins un sélecteur OSM (extraction active)."""
    return [f for f in SERVICE_FAMILIES if f.get("implemented")]


def _selector_pairs(family: dict) -> dict[str, list[str]]:
    """Agrège les sélecteurs de toutes les sous-catégories : osm_key -> valeurs triées uniques."""
    merged: dict[str, set[str]] = {}
    for sub in family.get("subcategories", []):
        for selector in sub.get("selectors", []):
            for osm_key, values in selector.items():
                merged.setdefault(osm_key, set()).update(values)
    return {key: sorted(values) for key, values in merged.items()}


def build_service_query(family: dict, bbox: str, timeout: int = 120) -> str | None:
    """
    Construit la requête Overpass d'une famille (nœuds + ways + relations).

    Renvoie None si la famille n'a aucun sélecteur exploitable : il n'y a alors
    rien à télécharger.
    """
    pairs = _selector_pairs(family)
    if not pairs:
        return None

    clauses: list[str] = []
    for osm_key, values in pairs.items():
        regex = "|".join(values)
        selector = f'["{osm_key}"~"^({regex})$"]'
        for kind in ("node", "way", "relation"):
            clauses.append(f"  {kind}{selector}({bbox});")

    body = "\n".join(clauses)
    return f"[out:json][timeout:{timeout}];\n(\n{body}\n);\nout center tags;"


def classify_service_element(family: dict, tags: dict) -> str | None:
    """
    Renvoie la clé de sous-catégorie correspondant aux tags (première qui matche
    dans l'ordre déclaré), ou None si aucune.
    """
    if not tags:
        return None

    for sub in family.get("subcategories", []):
        for selector in sub.get("selectors", []):
            for osm_key, values in selector.items():
                value = tags.get(osm_key)
                if value is not None and str(value) in values:
                    return sub["key"]
    return None


def service_point(element: dict) -> list | None:
    """
    Extrait un point [lat, lon] depuis un élément Overpass :
    - nœud : element['lat'], element['lon'] ;
    - way/relation : element['center'] (présent grâce à `out center`).
    Renvoie None si aucune position exploitable.
    """
    if element.get("type") == "node" and "lat" in element and "lon" in element:
        return [float(element["lat"]), float(element["lon"])]

    center = element.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return [float(center["lat"]), float(center["lon"])]

    return None


def subcategory_labels(family: dict) -> dict[str, str]:
    """Map clé de sous-catégorie -> libellé, pour les rapports/contrats."""
    return {sub["key"]: sub["label"] for sub in family.get("subcategories", [])}


def source_tag(family: dict, tags: dict) -> str:
    """Reconstruit un libellé de provenance OSM lisible (premier sélecteur matché)."""
    for sub in family.get("subcategories", []):
        for selector in sub.get("selectors", []):
            for osm_key, values in selector.items():
                value = tags.get(osm_key)
                if value is not None and str(value) in values:
                    return f"{osm_key}={value}"
    return ""
