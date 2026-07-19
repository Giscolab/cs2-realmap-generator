"""
overpass_client.py

Client Overpass API avec :
- plusieurs serveurs publics ;
- rotation automatique ;
- attente progressive ;
- messages lisibles en console.
"""

import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

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


def _create_ssl_context() -> ssl.SSLContext:
    """
    Construit un contexte TLS vérifié.

    Certaines distributions Python Windows autonomes n'embarquent aucun
    fichier CA et `urllib` échoue alors sur tous les endpoints HTTPS. On charge
    explicitement le magasin ROOT de Windows, sans désactiver la vérification.
    """
    context = ssl.create_default_context()

    if os.name == "nt" and hasattr(ssl, "enum_certificates"):
        for certificate, encoding, _trust in ssl.enum_certificates("ROOT"):
            if encoding != "x509_asn":
                continue
            try:
                context.load_verify_locations(
                    cadata=ssl.DER_cert_to_PEM_cert(certificate)
                )
            except (ssl.SSLError, ValueError):
                # Un certificat système illisible ne doit pas empêcher le
                # chargement des autres autorités de confiance.
                continue

    # Python 3.13+ active VERIFY_X509_STRICT par défaut. Plusieurs certificats
    # racine Windows historiques restent sûrs pour la chaîne/nom d'hôte mais
    # n'ont pas l'extension Basic Constraints marquée « critical ». Désactiver
    # ce contrôle de forme rétablit la compatibilité Windows tout en conservant
    # CERT_REQUIRED et la vérification du nom d'hôte.
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT

    return context


SSL_CONTEXT = _create_ssl_context()

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

                payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
                request = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers=HEADERS,
                    method="POST",
                )

                with urllib.request.urlopen(
                    request,
                    timeout=200,
                    context=SSL_CONTEXT,
                ) as response:
                    content = response.read()
                    status_code = response.getcode()

                if status_code == 200:
                    size_kb = len(content) / 1024
                    print(f"OK ({size_kb:.0f} Ko)")
                    return json.loads(content.decode("utf-8"))

                print(f"HTTP {status_code}")

            except (TimeoutError, socket.timeout):
                print("TIMEOUT")

            except urllib.error.HTTPError as error:
                print(f"HTTP {error.code}")

            except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as error:
                print(f"ERREUR : {str(error)[:80]}")

            time.sleep(wait_seconds)

        wait_seconds *= 2

    raise RuntimeError(f"Tous les serveurs Overpass ont échoué pour : {label}")
