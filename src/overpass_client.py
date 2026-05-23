"""
overpass_client.py

Client Overpass API avec :
- plusieurs serveurs publics ;
- rotation automatique ;
- attente progressive ;
- messages lisibles en console.
"""

import time
import requests

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

HEADERS = {
    "User-Agent": "CS2-Realmap-Generator/1.0 (OpenStreetMap Overpass client)",
    "Content-Type": "application/x-www-form-urlencoded",
}

ROAD_HIGHWAY_VALUES = "|".join((
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
))

PATH_HIGHWAY_VALUES = "|".join(("footway", "path", "steps", "pedestrian"))


def build_roads_query(bbox: str) -> str:
    """
    Construit la requête Overpass dédiée aux routes.

    DATA_ROADS ne garde que les voies routières utiles pour une lecture CS2.
    Les chemins piétons sont extraits séparément dans DATA_PATHS.
    """
    return f"""
[out:json][timeout:180];
way["highway"~"^({ROAD_HIGHWAY_VALUES})$"]({bbox});
out geom;
""".strip()


def build_paths_query(bbox: str) -> str:
    """
    Construit la requête Overpass dédiée aux chemins et rues piétonnes.
    """
    return f"""
[out:json][timeout:180];
way["highway"~"^({PATH_HIGHWAY_VALUES})$"]({bbox});
out geom;
""".strip()


def query_with_retry(query: str, label: str, max_attempts: int = 3) -> dict:
    """
    Envoie une requête Overpass QL avec réessais automatiques.

    Les serveurs Overpass publics peuvent répondre :
    - HTTP 429 : trop de requêtes ;
    - HTTP 504 : délai dépassé ;
    - timeout réseau.

    En cas d’échec, on essaie le serveur suivant.
    """
    wait_seconds = 3

    for attempt in range(1, max_attempts + 1):
        for endpoint in ENDPOINTS:
            host = endpoint.split("/")[2]

            try:
                print(f"  [{label}] {host} (essai {attempt})... ", end="", flush=True)

                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=200,
                )

                if response.status_code == 200:
                    size_kb = len(response.content) / 1024
                    print(f"OK ({size_kb:.0f} Ko)")
                    return response.json()

                print(f"HTTP {response.status_code}")

            except requests.exceptions.Timeout:
                print("TIMEOUT")

            except requests.exceptions.RequestException as error:
                print(f"ERREUR : {str(error)[:80]}")

            time.sleep(wait_seconds)

        wait_seconds *= 2

    raise RuntimeError(f"Tous les serveurs Overpass ont échoué pour : {label}")
