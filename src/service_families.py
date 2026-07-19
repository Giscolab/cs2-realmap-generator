"""
service_families.py — Familles de services CS2 extraites d'OpenStreetMap.

Source unique de vérité pour les familles de services affichées par le HUD
CityTimelineMod (Éducation, Électricité, Pompiers, Déchets, Médical, Transports,
Eau/égouts, Communications, Parcs).

Les services OSM sont le plus souvent des *nœuds* (amenity=...), parfois des
surfaces (way/relation). On extrait donc UN POINT représentatif par élément :
- nœud  -> sa position (lat/lon) ;
- way/relation -> le `center` renvoyé par Overpass (`out center`).

La classification est volontairement conservatrice, mais elle exploite les tags
secondaires OSM (`isced:level`, `station`, `generator:source`, etc.) et quelques
indices de nom non ambigus. Les règles prioritaires passent avant les sélecteurs
génériques : une station `railway=station + station=subway` ne devient donc plus
une gare ferroviaire et une école nommée « High School » ne tombe plus dans le
primaire.

Les données produites restent exclusivement visuelles et informatives. Ce module
ne contient aucun mapping vers un prefab, un spawner ou un réseau du jeu.
"""

from __future__ import annotations

import re
import unicodedata


# Une "famille" = {key, label, implemented, subcategories[]}
# Une "sous-catégorie" = {key, label, priority, selectors[]}
#
# Un sélecteur simple garde la forme {osm_key: [valeurs acceptées]}. Les règles
# enrichies peuvent combiner :
# - all / any / none : correspondances exactes ;
# - any_tokens : valeurs OSM séparées par ";", "," ou "|" ;
# - name_contains : fragments de nom normalisés (casse/accents ignorés) ;
# - numeric_gte : seuil numérique minimal.
SERVICE_FAMILIES: list[dict] = [
    {
        "key": "education",
        "label": "Éducation et recherche",
        "implemented": True,
        "subcategories": [
            {"key": "primary", "label": "École primaire", "priority": 10,
             "selectors": [
                 {"amenity": ["kindergarten", "childcare"]},
                 {"all": {"amenity": ["school"]},
                  "any": {"school": ["primary", "elementary", "junior"],
                          "school:level": ["primary", "elementary"],
                          "education": ["primary", "elementary"]}},
                 {"all": {"amenity": ["school"]},
                  "any_tokens": {"isced:level": ["0", "1"]}},
                 # Fallback : amenity=school reste visible même si le niveau
                 # n'est pas renseigné. Les règles secondary/university ont une
                 # priorité supérieure et sont évaluées avant celle-ci.
                 {"amenity": ["school"]},
             ]},
            {"key": "secondary", "label": "Collège / lycée", "priority": 80,
             "selectors": [
                 {"all": {"amenity": ["school"]},
                  "any": {"school": ["secondary", "middle", "high_school", "junior_high", "senior_high"],
                          "school:level": ["secondary", "middle", "high"],
                          "education": ["secondary", "middle", "high_school"],
                          "education:level": ["secondary"]}},
                 {"all": {"amenity": ["school"]},
                  "any_tokens": {"isced:level": ["2", "3", "4"]}},
                 {"all": {"amenity": ["school"]}, "numeric_gte": {"min_age": 11}},
                 {"all": {"amenity": ["school"]}, "numeric_gte": {"grades": 7}},
                 {"all": {"amenity": ["school"]}, "numeric_gte": {"school:grades": 7}},
                 {"all": {"amenity": ["school"]},
                  "name_contains": [
                      "high school", "secondary school", "middle school",
                      "junior high", "senior high", "senior secondary",
                      "lycée", "lycee", "college secondaire",
                      "gymnasium", "secundaria", "liceo", "hoërskool",
                      "hoerskool", "sekondêr", "sekondere skool",
                  ]},
             ]},
            {"key": "university", "label": "Université", "priority": 90,
             "selectors": [
                 {"amenity": ["university", "college"]},
                 {"education": ["tertiary", "higher_education"]},
                 {"all": {"amenity": ["school"]},
                  "any_tokens": {"isced:level": ["5", "6", "7", "8"]}},
             ]},
            {"key": "research", "label": "Recherche", "priority": 100,
             "selectors": [
                 {"amenity": ["research_institute"]},
                 {"office": ["research"]},
                 {"research_institution": ["yes", "institute", "laboratory"]},
                 {"landuse": ["research"]},
             ]},
        ],
    },
    {
        "key": "fire",
        "label": "Sapeurs-pompiers",
        "implemented": True,
        "subcategories": [
            {"key": "local_station", "label": "Caserne locale", "priority": 10,
             "selectors": [
                 {"amenity": ["fire_station"]},
                 {"emergency": ["fire_station"]},
             ]},
            {"key": "large_station", "label": "Grande caserne", "priority": 100,
             "selectors": [
                 {"fire_station": ["headquarters", "headquarter", "central", "regional"]},
                 {"all": {"amenity": ["fire_station"]},
                  "any": {"fire_station:type": ["headquarters", "headquarter", "central", "regional", "metropolitan", "training_centre"]}},
                 {"all": {"amenity": ["fire_station"]},
                  "numeric_gte": {"capacity:fire_engines": 4}},
                 {"all": {"amenity": ["fire_station"]},
                  "name_contains": [
                      "fire service headquarters", "fire brigade headquarters",
                      "fire and rescue headquarters", "central fire station",
                      "fire service hq", "fire brigade hq",
                  ]},
             ]},
            {"key": "special_rescue", "label": "Surveillance / secours spécialisés", "priority": 110,
             "selectors": [
                 {"emergency": [
                     "water_rescue_station", "water_rescue", "lifeguard",
                     "lifeguard_base", "lifeguard_tower", "mountain_rescue",
                     "search_and_rescue", "rescue_station",
                 ]},
                 {"amenity": ["rescue_station", "coast_guard"]},
                 {"lifeguard": ["base", "tower", "platform"]},
             ]},
        ],
    },
    {
        "key": "medical",
        "label": "Services médicaux et soins mortuaires",
        "implemented": True,
        "subcategories": [
            {"key": "clinic", "label": "Clinique", "priority": 70,
             "selectors": [
                 {"amenity": ["clinic", "doctors", "dentist"]},
                 {"healthcare": ["clinic", "doctor", "dentist", "centre", "center"]},
             ]},
            {"key": "hospital", "label": "Hôpital", "priority": 90,
             "selectors": [{"amenity": ["hospital"]}, {"healthcare": ["hospital"]}]},
            {"key": "crematorium", "label": "Crématorium", "priority": 80,
             "selectors": [{"amenity": ["crematorium"]}]},
            {"key": "cemetery", "label": "Cimetière", "priority": 60,
             "selectors": [{"amenity": ["grave_yard"]}, {"landuse": ["cemetery"]}]},
        ],
    },
    {
        "key": "parks",
        "label": "Parcs et loisirs",
        "implemented": True,
        "subcategories": [
            {"key": "local_park", "label": "Parc local", "priority": 10,
             "selectors": [{"leisure": ["park", "garden", "dog_park"]}]},
            {"key": "large_park", "label": "Grand parc", "priority": 100,
             "selectors": [
                 {"leisure": ["nature_reserve"]},
                 {"boundary": ["national_park", "protected_area"]},
                 {"all": {"leisure": ["park"]},
                  "any": {"park:type": ["regional", "metropolitan", "national", "state"]}},
             ]},
            {"key": "sport", "label": "Sport", "priority": 80,
             "selectors": [{"leisure": [
                 "sports_centre", "sports_hall", "fitness_centre", "stadium",
                 "pitch", "track", "swimming_pool", "golf_course", "horse_riding",
             ]}]},
            {"key": "leisure", "label": "Loisirs", "priority": 60,
             "selectors": [{"leisure": [
                 "playground", "recreation_ground", "water_park", "marina",
                 "fishing", "amusement_arcade", "beach_resort",
             ]}]},
            {"key": "tourism", "label": "Tourisme", "priority": 70,
             "selectors": [{"tourism": [
                 "attraction", "museum", "gallery", "zoo", "aquarium",
                 "theme_park", "viewpoint", "information",
             ]}]},
        ],
    },

    {"key": "electricity", "label": "Électricité", "implemented": True, "subcategories": [
        {"key": "generation", "label": "Production électrique", "priority": 90,
         "selectors": [{"power": ["plant", "generator", "heliostat"]}]},
        {"key": "transformation", "label": "Transformation", "priority": 100,
         "selectors": [{"power": ["substation", "transformer", "converter", "compensator", "switchgear"]}]},
        {"key": "storage", "label": "Stockage", "priority": 120,
         "selectors": [
             {"power": ["storage"]},
             {"man_made": ["battery_storage", "energy_storage"]},
             {"all": {"power": ["plant", "generator"]},
              "any_tokens": {"plant:source": ["battery", "storage", "flywheel", "pumped_storage", "hydrogen"],
                             "generator:source": ["battery", "storage", "flywheel", "pumped_storage", "hydrogen"],
                             "plant:method": ["water-pumped-storage", "pumped-storage", "pumped_storage"],
                             "generator:method": ["water-pumped-storage", "pumped-storage", "pumped_storage"],
                             "storage": ["battery", "electricity", "energy"]}},
         ]},
        {"key": "grid", "label": "Réseau électrique", "priority": 80,
         "selectors": [{"power": [
             "line", "minor_line", "cable", "tower", "pole", "portal",
             "busbar", "bay", "switch", "insulator", "terminal", "connection",
             "cable_distribution_cabinet", "marker",
         ]}]},
    ]},
    {"key": "waste", "label": "Gestion des déchets", "implemented": True, "subcategories": [
        {"key": "collection", "label": "Collecte", "priority": 70,
         "selectors": [{"amenity": [
             "waste_disposal", "waste_transfer_station", "waste_basket",
             "sanitary_dump_station",
         ]}]},
        {"key": "recycling", "label": "Recyclage", "priority": 80,
         "selectors": [{"amenity": ["recycling", "recycling_station"]}]},
        {"key": "treatment", "label": "Traitement", "priority": 90,
         "selectors": [
             {"man_made": ["incinerator", "wastewater_plant", "wastewater_treatment_plant"]},
             {"industrial": ["waste", "waste_processing", "recycling"]},
         ]},
        {"key": "landfill", "label": "Décharge / stockage", "priority": 100,
         "selectors": [{"landuse": ["landfill"]}, {"man_made": ["landfill"]}]},
    ]},
    {"key": "transport", "label": "Transports", "implemented": True, "subcategories": [
        {"key": "bus", "label": "Bus", "priority": 100,
         "selectors": [
             {"highway": ["bus_stop"]},
             {"amenity": ["bus_station"]},
             {"all": {"public_transport": ["platform", "station", "stop_position"]},
              "any": {"bus": ["yes"], "bus_station": ["yes"]}},
         ]},
        {"key": "tram", "label": "Tram", "priority": 120,
         "selectors": [
             {"railway": ["tram_stop"]},
             {"station": ["tram", "light_rail"]},
             {"all": {"public_transport": ["platform", "station", "stop_position"]},
              "any": {"tram": ["yes"], "light_rail": ["yes"]}},
         ]},
        {"key": "train", "label": "Train", "priority": 110,
         "selectors": [
             {"all": {"railway": ["station", "halt"]},
              "none": {"station": ["subway", "tram", "light_rail"],
                       "subway": ["yes"], "tram": ["yes"], "light_rail": ["yes"]}},
             {"all": {"public_transport": ["station", "platform", "stop_position"]},
              "any": {"train": ["yes"]},
              "none": {"subway": ["yes"], "tram": ["yes"], "light_rail": ["yes"]}},
         ]},
        {"key": "metro", "label": "Métro", "priority": 130,
         "selectors": [
             {"railway": ["subway_entrance"]},
             {"station": ["subway"]},
             {"subway": ["yes"]},
             {"all": {"public_transport": ["platform", "station", "stop_position"]},
              "any": {"subway": ["yes"]}},
         ]},
        {"key": "taxi", "label": "Taxi", "priority": 90,
         "selectors": [
             {"amenity": ["taxi"]},
             {"all": {"public_transport": ["platform", "station"]}, "any": {"taxi": ["yes"]}},
         ]},
        {"key": "air", "label": "Aérien", "priority": 90,
         "selectors": [{"aeroway": ["aerodrome", "airport", "terminal", "helipad", "heliport"]}]},
        {"key": "maritime", "label": "Maritime", "priority": 115,
         "selectors": [
             {"amenity": ["ferry_terminal"]},
             {"all": {"public_transport": ["station", "platform", "stop_position"]},
              "any": {"ferry": ["yes"]}},
             {"harbour": ["yes", "ferry_terminal"]},
             {"seamark:type": ["harbour"]},
         ]},
    ]},
    {"key": "water", "label": "Eau et égouts", "implemented": True, "subcategories": [
        {"key": "pumping", "label": "Pompage", "priority": 90,
         "selectors": [
             {"man_made": ["pump", "water_tower", "water_well"]},
             {"all": {"man_made": ["pumping_station"]},
              "none": {"pumping_station": ["sewage", "wastewater"],
                       "utility": ["sewerage", "wastewater"]}},
             {"all": {"utility": ["water"]},
              "any": {"man_made": ["pumping_station", "pump"]}},
         ]},
        {"key": "water_treatment", "label": "Traitement de l'eau", "priority": 110,
         "selectors": [
             {"man_made": ["water_works", "water_treatment", "water_treatment_plant"]},
             {"industrial": ["water_works", "water_treatment"]},
             {"amenity": ["water_works"]},
         ]},
        {"key": "sewage", "label": "Égouts", "priority": 100,
         "selectors": [
             {"waterway": ["drain", "ditch"]},
             {"man_made": ["sewer", "sewer_vent", "storm_drain", "outfall"]},
             {"utility": ["sewerage", "sewage"]},
             {"pumping_station": ["sewage", "wastewater"]},
             {"amenity": ["sanitary_dump_station"]},
         ]},
        {"key": "wastewater", "label": "Traitement des eaux usées", "priority": 120,
         "selectors": [
             {"man_made": ["wastewater_plant", "wastewater_treatment_plant", "sewage_works"]},
             {"industrial": ["wastewater", "sewage_works"]},
             {"amenity": ["wastewater_plant"]},
             {"wastewater": ["plant", "treatment_plant"]},
             {"all": {"man_made": ["water_works"]},
              "any": {"water_works": ["wastewater", "sewage"]}},
         ]},
    ]},
    {"key": "communications", "label": "Communications", "implemented": True, "subcategories": [
        {"key": "post", "label": "Poste", "priority": 80,
         "selectors": [
             {"amenity": ["post_office", "post_box", "post_depot", "parcel_locker"]},
             {"office": ["courier", "postal_service"]},
         ]},
        {"key": "telecom", "label": "Télécommunications", "priority": 100,
         "selectors": [
             {"telecom": [
                 "exchange", "service_device", "connection_point", "distribution_point",
                 "street_cabinet", "line", "central_office",
             ]},
             {"man_made": ["telephone_exchange", "telecommunication_tower"]},
             {"building": ["telephone_exchange", "telecommunications"]},
             {"all": {"man_made": ["street_cabinet"]},
              "any": {"street_cabinet": ["telecom"], "utility": ["telecom", "telecommunications"]}},
             {"utility": ["telecom", "telecommunications"]},
         ]},
        {"key": "datacenter", "label": "Serveurs / data center", "priority": 120,
         "selectors": [
             {"building": ["data_center", "data_centre", "server_farm"]},
             {"man_made": ["data_center", "data_centre", "server_farm"]},
             {"telecom": ["data_center", "data_centre"]},
             {"industrial": ["data_center", "data_centre"]},
             {"amenity": ["data_center", "data_centre"]},
         ]},
        {"key": "radio", "label": "Radio / antennes", "priority": 110,
         "selectors": [
             {"man_made": ["antenna", "communications_tower", "mast"]},
             {"tower:type": ["communication", "broadcasting", "radio", "microwave"]},
             {"communication:mobile_phone": ["yes"]},
             {"communication:radio": ["yes"]},
             {"communication:microwave": ["yes"]},
         ]},
    ]},
]


# Propriétés utiles conservées dans chaque Feature GeoJSON. La liste est
# volontairement informative : aucune donnée de placement CS2 n'y figure.
SERVICE_TAG_KEYS = (
    "name", "official_name", "short_name", "operator", "operator:type", "network", "ref",
    "amenity", "healthcare", "emergency", "lifeguard",
    "fire_station", "fire_station:type", "capacity", "capacity:fire_engines",
    "building", "building:levels", "school", "school:level", "education",
    "education:level", "isced:level", "grades", "school:grade", "school:grades",
    "min_age", "max_age", "research_institution", "office",
    "leisure", "park:type", "boundary", "tourism", "landuse", "sport",
    "power", "generator:source", "plant:source", "generator:method",
    "plant:method", "storage", "industrial", "waste", "recycling_type",
    "man_made", "highway", "railway", "station", "public_transport",
    "bus", "bus_station", "tram", "train", "subway", "light_rail", "taxi",
    "aeroway", "ferry", "harbour", "seamark:type", "waterway", "water",
    "water_works", "wastewater", "pumping_station", "utility", "sewerage",
    "telecom", "street_cabinet", "tower:type", "communication:mobile_phone",
    "communication:radio", "communication:microwave",
)


def implemented_families() -> list[dict]:
    """Familles possédant au moins un sélecteur OSM (extraction active)."""
    return [f for f in SERVICE_FAMILIES if f.get("implemented")]


_SELECTOR_OPERATORS = {"all", "any", "any_tokens", "none", "name_contains", "numeric_gte"}


def _normalized_value(value: object) -> str:
    return str(value).strip().casefold()


def _normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _allowed_values(values: object) -> tuple:
    if isinstance(values, (list, tuple, set, frozenset)):
        return tuple(values)
    return (values,)


def _exact_match(tags: dict, osm_key: str, values: object) -> bool:
    value = tags.get(osm_key)
    if value is None:
        return False
    normalized = _normalized_value(value)
    return any(normalized == _normalized_value(allowed) for allowed in _allowed_values(values))


def _all_exact(tags: dict, conditions: dict) -> bool:
    return bool(conditions) and all(
        _exact_match(tags, osm_key, values)
        for osm_key, values in conditions.items()
    )


def _any_exact(tags: dict, conditions: dict) -> bool:
    return bool(conditions) and any(
        _exact_match(tags, osm_key, values)
        for osm_key, values in conditions.items()
    )


def _token_match(tags: dict, osm_key: str, values: object) -> bool:
    value = tags.get(osm_key)
    if value is None:
        return False
    tokens = {
        _normalized_value(token)
        for token in re.split(r"[;,|]", str(value))
        if str(token).strip()
    }
    accepted = {_normalized_value(allowed) for allowed in _allowed_values(values)}
    return bool(tokens & accepted)


def _any_token(tags: dict, conditions: dict) -> bool:
    return bool(conditions) and any(
        _token_match(tags, osm_key, values)
        for osm_key, values in conditions.items()
    )


def _numeric_at_least(tags: dict, conditions: dict) -> bool:
    if not conditions:
        return False
    for osm_key, minimum in conditions.items():
        raw_value = tags.get(osm_key)
        if raw_value is None:
            return False
        values = re.findall(r"\d+(?:[.,]\d+)?", str(raw_value))
        if not values or max(float(value.replace(",", ".")) for value in values) < float(minimum):
            return False
    return True


def _name_contains(tags: dict, fragments: object) -> bool:
    names = [
        _normalized_name(tags.get(key, ""))
        for key in ("name", "official_name", "short_name")
    ]
    needles = [_normalized_name(fragment) for fragment in _allowed_values(fragments)]
    return any(needle and needle in name for name in names for needle in needles)


def _matches_selector(tags: dict, selector: dict) -> bool:
    """Évalue un sélecteur simple ou une règle conditionnelle enrichie."""
    if not selector:
        return False

    if not (_SELECTOR_OPERATORS & selector.keys()):
        # Les sélecteurs historiques ne contiennent actuellement qu'une clé,
        # mais une éventuelle forme multi-clés est interprétée comme un ET.
        return _all_exact(tags, selector)

    has_positive_condition = False

    all_conditions = selector.get("all")
    if all_conditions is not None:
        has_positive_condition = True
        if not _all_exact(tags, all_conditions):
            return False

    any_conditions = selector.get("any")
    if any_conditions is not None:
        has_positive_condition = True
        if not _any_exact(tags, any_conditions):
            return False

    token_conditions = selector.get("any_tokens")
    if token_conditions is not None:
        has_positive_condition = True
        if not _any_token(tags, token_conditions):
            return False

    name_fragments = selector.get("name_contains")
    if name_fragments is not None:
        has_positive_condition = True
        if not _name_contains(tags, name_fragments):
            return False

    numeric_conditions = selector.get("numeric_gte")
    if numeric_conditions is not None:
        has_positive_condition = True
        if not _numeric_at_least(tags, numeric_conditions):
            return False

    excluded = selector.get("none")
    if excluded and _any_exact(tags, excluded):
        return False

    return has_positive_condition


def _subcategories_by_priority(family: dict) -> list[dict]:
    """Retourne l'ordre de classification sans changer l'ordre d'affichage HUD."""
    return sorted(
        family.get("subcategories", []),
        key=lambda sub: int(sub.get("priority", 0)),
        reverse=True,
    )


def _queryable_maps(selector: dict) -> list[dict]:
    """Parties exactes d'une règle traduisibles en filtres Overpass."""
    if not (_SELECTOR_OPERATORS & selector.keys()):
        return [selector]
    return [
        conditions
        for operator in ("all", "any", "any_tokens")
        if isinstance((conditions := selector.get(operator)), dict)
    ]


def _selector_pairs(family: dict) -> dict[str, list[str]]:
    """Agrège les sélecteurs de toutes les sous-catégories : osm_key -> valeurs triées uniques."""
    merged: dict[str, set[str]] = {}
    for sub in family.get("subcategories", []):
        for selector in sub.get("selectors", []):
            for conditions in _queryable_maps(selector):
                for osm_key, values in conditions.items():
                    merged.setdefault(osm_key, set()).update(
                        str(value) for value in _allowed_values(values)
                    )
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
        regex = "|".join(re.escape(value) for value in values)
        selector = f'["{osm_key}"~"^({regex})$"]'
        for kind in ("node", "way", "relation"):
            clauses.append(f"  {kind}{selector}({bbox});")

    body = "\n".join(clauses)
    return f"[out:json][timeout:{timeout}];\n(\n{body}\n);\nout center tags;"


def classify_service_element(family: dict, tags: dict) -> str | None:
    """
    Renvoie la clé de sous-catégorie correspondant aux tags. Les priorités
    empêchent les fallbacks génériques de masquer une règle plus précise.
    """
    if not tags:
        return None

    for sub in _subcategories_by_priority(family):
        for selector in sub.get("selectors", []):
            if _matches_selector(tags, selector):
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


def service_tags(tags: dict) -> dict:
    """Conserve les tags OSM informatifs utiles au HUD et aux exports."""
    return {
        osm_key: tags[osm_key]
        for osm_key in SERVICE_TAG_KEYS
        if tags.get(osm_key) not in (None, "")
    }


def _matching_source_pair(selector: dict, tags: dict) -> tuple[str, object] | None:
    if not _matches_selector(tags, selector):
        return None

    if not (_SELECTOR_OPERATORS & selector.keys()):
        discriminating_maps = [selector]
        fallback_maps: list[dict] = []
    else:
        # Les conditions discriminantes sont préférées au socle générique
        # (`school=secondary` avant `amenity=school`).
        discriminating_maps = [
            conditions
            for operator in ("any", "any_tokens", "numeric_gte")
            if isinstance((conditions := selector.get(operator)), dict)
        ]
        fallback_maps = [selector["all"]] if isinstance(selector.get("all"), dict) else []

    for conditions in discriminating_maps:
        for osm_key, values in conditions.items():
            if osm_key in tags and (
                _exact_match(tags, osm_key, values)
                or _token_match(tags, osm_key, values)
                or (
                    conditions is selector.get("numeric_gte")
                    and _numeric_at_least(tags, {osm_key: values})
                )
            ):
                return osm_key, tags[osm_key]

    if selector.get("name_contains") is not None:
        for osm_key in ("name", "official_name", "short_name"):
            if tags.get(osm_key):
                return osm_key, tags[osm_key]

    for conditions in fallback_maps:
        for osm_key, values in conditions.items():
            if _exact_match(tags, osm_key, values):
                return osm_key, tags[osm_key]

    return None


def source_tag(family: dict, tags: dict) -> str:
    """Reconstruit la provenance OSM de la règle de classification retenue."""
    classified = classify_service_element(family, tags)
    if classified is None:
        return ""

    for sub in _subcategories_by_priority(family):
        if sub["key"] != classified:
            continue
        for selector in sub.get("selectors", []):
            pair = _matching_source_pair(selector, tags)
            if pair is not None:
                return f"{pair[0]}={pair[1]}"
    return ""
