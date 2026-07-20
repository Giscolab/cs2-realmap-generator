"""
cs2_zones.py

Définition des zones CS2 et construction des requêtes Overpass.

Format BBOX attendu par Overpass :
"sud,ouest,nord,est"
soit :
"latitude_min,longitude_min,latitude_max,longitude_max"

Exemple Paris :
"48.766147,2.161560,48.945053,2.485657"
"""

CS2_LABELS = {
    "res_high":    "Résidentiel haute densité",
    "res_med":     "Résidentiel moyenne densité",
    "res_low":     "Résidentiel basse densité",
    "com_high":    "Commercial haute densité",
    "com_low":     "Commercial basse densité",
    "retail":      "Commerce de détail",
    "industrial":  "Industrie",
    "prk_ramp":    "Parking en ouvrage",
    "prk_surface": "Parking de surface",
    "office":      "Bureaux / administration",
    "mixed":       "Usage mixte",
}

# Ville d’exemple historique du projet d’origine.
# Ne doit plus être utilisée comme valeur implicite dans le pipeline.
EXAMPLE_BBOX_MINNEAPOLIS = "44.86,-93.38,45.05,-93.17"

# Exemple utile pour développement local / tests Europe.
EXAMPLE_BBOX_PARIS = "48.766147,2.161560,48.945053,2.485657"


def build_queries(bbox: str) -> dict:
    """
    Construit les requêtes Overpass QL pour une boîte géographique donnée.

    Les requêtes sont séparées par catégorie au lieu d’utiliser une seule
    requête géante, car les serveurs Overpass publics limitent souvent les
    grosses requêtes.

    La requête buildings_levels est exécutée en premier afin de construire
    un index de densité utilisé par la classification résidentielle.
    """
    return {
        "buildings_levels": f"""
[out:json][timeout:120];
(
  way["building"]["building:levels"]({bbox});
  relation["building"]["building:levels"]({bbox});
);
out ids tags;
""".strip(),

        "residential": f"""
[out:json][timeout:180];
(
  way["landuse"="residential"]({bbox});
  relation["landuse"="residential"]({bbox});
  way["building"~"^(apartments|residential|house|detached|semidetached_house|terrace|townhouse|dormitory|bungalow|static_caravan)$"]({bbox});
  relation["building"~"^(apartments|residential|house|detached|semidetached_house|terrace|townhouse|dormitory|bungalow|static_caravan)$"]({bbox});
);
out geom;
""".strip(),

        "commercial": f"""
[out:json][timeout:180];
(
  way["landuse"="commercial"]({bbox});
  relation["landuse"="commercial"]({bbox});
  way["building"~"^(commercial|retail|mall)$"]({bbox});
  relation["building"~"^(commercial|retail|mall)$"]({bbox});
  way["shop"]({bbox});
  relation["shop"]({bbox});
  way["amenity"="marketplace"]({bbox});
  relation["amenity"="marketplace"]({bbox});
);
out geom;
""".strip(),

        "industrial": f"""
[out:json][timeout:180];
(
  way["landuse"="industrial"]({bbox});
  relation["landuse"="industrial"]({bbox});
  way["building"~"^(industrial|warehouse|factory)$"]({bbox});
  relation["building"~"^(industrial|warehouse|factory)$"]({bbox});
  way["industrial"]({bbox});
  relation["industrial"]({bbox});
);
out geom;
""".strip(),

        "retail": f"""
[out:json][timeout:180];
(
  way["landuse"="retail"]({bbox});
  relation["landuse"="retail"]({bbox});
);
out geom;
""".strip(),

        "parking": f"""
[out:json][timeout:180];
(
  way["amenity"="parking"]({bbox});
  relation["amenity"="parking"]({bbox});
);
out geom;
""".strip(),

        "office": f"""
[out:json][timeout:180];
(
  way["building"="office"]({bbox});
  relation["building"="office"]({bbox});
  way["office"]({bbox});
  relation["office"]({bbox});
  way["landuse"="office"]({bbox});
);
out geom;
""".strip(),

        "mixed": f"""
[out:json][timeout:180];
(
  way["landuse"~"^(mixed|mixed_use)$"]({bbox});
  relation["landuse"~"^(mixed|mixed_use)$"]({bbox});
  way["building"~"^(mixed|mixed-use|mixed_use)$"]({bbox});
  relation["building"~"^(mixed|mixed-use|mixed_use)$"]({bbox});
  way["mixed_use"="yes"]({bbox});
  relation["mixed_use"="yes"]({bbox});
  way["building:use"~"(apartments|residential)"]["building:use"~"(commercial|office|retail|shop)"]({bbox});
  relation["building:use"~"(apartments|residential)"]["building:use"~"(commercial|office|retail|shop)"]({bbox});
  way["building"~"^(apartments|residential|house|terrace|townhouse)$"]["shop"]({bbox});
  relation["building"~"^(apartments|residential|house|terrace|townhouse)$"]["shop"]({bbox});
  way["building"~"^(apartments|residential|house|terrace|townhouse)$"]["office"]({bbox});
  relation["building"~"^(apartments|residential|house|terrace|townhouse)$"]["office"]({bbox});
);
out geom;
""".strip(),
    }
