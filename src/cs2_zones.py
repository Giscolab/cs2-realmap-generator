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
way["building"="apartments"]["building:levels"]({bbox});
out ids tags;
""".strip(),

        "residential": f"""
[out:json][timeout:180];
(
  way["landuse"="residential"]({bbox});
  relation["landuse"="residential"]({bbox});
);
out geom;
""".strip(),

        "commercial": f"""
[out:json][timeout:180];
(
  way["landuse"="commercial"]({bbox});
  relation["landuse"="commercial"]({bbox});
);
out geom;
""".strip(),

        "industrial": f"""
[out:json][timeout:180];
(
  way["landuse"="industrial"]({bbox});
  relation["landuse"="industrial"]({bbox});
  way["building"~"^(industrial|warehouse|factory)$"]({bbox});
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
  way["landuse"="mixed"]({bbox});
  relation["landuse"="mixed"]({bbox});
  way["building"="mixed_use"]({bbox});
  relation["building"="mixed_use"]({bbox});
);
out geom;
""".strip(),
    }