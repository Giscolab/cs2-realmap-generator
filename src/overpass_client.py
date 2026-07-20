"""
overpass_client.py

Client Overpass API avec :
- plusieurs serveurs publics ;
- rotation automatique ;
- attente progressive ;
- messages lisibles en console.
"""

import hashlib
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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

PATH_HIGHWAY_TYPES = (
    "pedestrian",
    "footway",
    "path",
    "steps",
    "cycleway",
    "bridleway",
    "corridor",
    "platform",
)

PATH_HIGHWAY_VALUES = "|".join(PATH_HIGHWAY_TYPES)

# Les états de cycle de vie ne décrivent pas un réseau utilisable. Toutes les
# autres valeurs highway=* sont conservées dans roads.geojson et aboutissent à
# la catégorie HUD « Route non classée » si elles n'ont pas de classe dédiée.
# Ce fallback est important : une liste blanche figée perdait notamment
# highway=road, highway=track et toute nouvelle valeur OSM.
INACTIVE_HIGHWAY_TYPES = (
    "abandoned",
    "construction",
    "disused",
    "planned",
    "proposed",
    "razed",
)

INACTIVE_HIGHWAY_VALUES = "|".join(INACTIVE_HIGHWAY_TYPES)

_BBOX_PATTERN = re.compile(
    r"\(\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*,"
    r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*,"
    r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*,"
    r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*\)"
)


def build_roads_query(bbox: str) -> str:
    """
    Construit la requête Overpass dédiée aux routes.

    Toutes les voies highway=* actives sont conservées. Les chemins sont
    extraits séparément et exclus ici afin qu'une géométrie ne soit pas
    dupliquée dans roads.geojson et paths.geojson.
    """
    return f"""
[out:json][timeout:180];
way["highway"]
   ["highway"!~"^({PATH_HIGHWAY_VALUES})$"]
   ["highway"!~"^({INACTIVE_HIGHWAY_VALUES})$"]({bbox});
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


def _cache_file(query: str, label: str, cache_dir: str | Path) -> Path:
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    safe_label = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in str(label)
    ).strip("._") or "query"
    return Path(cache_dir) / f"{safe_label}-{query_hash}.json"


def _read_cached_response(path: Path, query: str) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    expected_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    if not isinstance(payload, dict) or payload.get("querySha256") != expected_hash:
        return None

    response = payload.get("response")
    if not isinstance(response, dict) or not isinstance(response.get("elements"), list):
        return None

    return response


def _write_cached_response(path: Path, query: str, label: str, response: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "label": label,
        "querySha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "cachedAt": datetime.now(timezone.utc).isoformat(),
        "response": response,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _split_query_bbox(query: str) -> list[str] | None:
    """Découpe en quatre une requête dont toutes les clauses partagent la bbox.

    Cette reprise adaptative est utilisée uniquement après l'échec de tous les
    endpoints. Elle rend les grosses villes extractibles sans maintenir à la
    main une variante de chaque requête Overpass.
    """
    matches = list(_BBOX_PATTERN.finditer(query))
    if not matches:
        return None

    bboxes = {tuple(float(value) for value in match.groups()) for match in matches}
    if len(bboxes) != 1:
        return None

    south, west, north, east = next(iter(bboxes))
    if not (south < north and west < east):
        return None

    middle_lat = (south + north) / 2.0
    middle_lon = (west + east) / 2.0
    tiles = (
        (south, west, middle_lat, middle_lon),
        (south, middle_lon, middle_lat, east),
        (middle_lat, west, north, middle_lon),
        (middle_lat, middle_lon, north, east),
    )
    split_queries = []
    for tile in tiles:
        replacement = "(" + ",".join(f"{value:.9f}" for value in tile) + ")"
        split_queries.append(_BBOX_PATTERN.sub(replacement, query))
    return split_queries


def _merge_overpass_responses(responses: list[dict]) -> dict:
    merged = dict(responses[0]) if responses else {}
    elements = []
    seen: set[tuple[str, object]] = set()

    for response in responses:
        for element in response.get("elements") or []:
            key = (str(element.get("type") or ""), element.get("id"))
            if element.get("id") is not None and key in seen:
                continue
            if element.get("id") is not None:
                seen.add(key)
            elements.append(element)

    merged["elements"] = elements
    return merged


def query_with_retry(
    query: str,
    label: str,
    max_attempts: int = 3,
    *,
    cache_dir: str | Path | None = None,
    refresh_cache: bool = False,
    split_bbox_on_failure: bool = False,
    max_split_depth: int = 2,
    _split_depth: int = 0,
) -> dict:
    """
    Envoie une requête Overpass QL avec réessais automatiques.

    Les serveurs Overpass publics peuvent répondre :
    - HTTP 429 : trop de requêtes ;
    - HTTP 504 : délai dépassé ;
    - timeout réseau.

    En cas d’échec, on essaie le serveur suivant.

    Si ``cache_dir`` (ou ``CS2_OVERPASS_CACHE_DIR``) est défini, chaque réponse
    réussie est écrite atomiquement sous une clé SHA-256 de la requête. Une
    relance reprend ainsi toutes les couches déjà téléchargées, tandis qu'une
    modification de la requête invalide naturellement l'ancienne entrée.
    """
    effective_cache_dir = cache_dir or os.environ.get("CS2_OVERPASS_CACHE_DIR")
    cache_path = (
        _cache_file(query, label, effective_cache_dir)
        if effective_cache_dir
        else None
    )

    if cache_path is not None and not refresh_cache:
        cached = _read_cached_response(cache_path, query)
        if cached is not None:
            print(f"  [{label}] cache local... OK ({len(cached['elements'])} éléments)")
            return cached

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
                    response_data = json.loads(content.decode("utf-8"))
                    if not isinstance(response_data, dict) or not isinstance(
                        response_data.get("elements"), list
                    ):
                        raise ValueError("Réponse Overpass sans liste elements")

                    if cache_path is not None:
                        try:
                            _write_cached_response(cache_path, query, label, response_data)
                        except OSError as error:
                            print(f"  [{label}] cache non écrit : {str(error)[:80]}")

                    return response_data

                print(f"HTTP {status_code}")

            except (TimeoutError, socket.timeout):
                print("TIMEOUT")

            except urllib.error.HTTPError as error:
                print(f"HTTP {error.code}")

            except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as error:
                print(f"ERREUR : {str(error)[:80]}")

            time.sleep(wait_seconds)

        wait_seconds *= 2

    if split_bbox_on_failure and _split_depth < max_split_depth:
        split_queries = _split_query_bbox(query)
        if split_queries:
            print(
                f"  [{label}] découpage adaptatif de la bbox "
                f"(niveau {_split_depth + 1}/{max_split_depth})"
            )
            responses = [
                query_with_retry(
                    split_query,
                    f"{label}:tuile-{index + 1}",
                    max_attempts,
                    cache_dir=effective_cache_dir,
                    refresh_cache=refresh_cache,
                    split_bbox_on_failure=True,
                    max_split_depth=max_split_depth,
                    _split_depth=_split_depth + 1,
                )
                for index, split_query in enumerate(split_queries)
            ]
            merged_response = _merge_overpass_responses(responses)
            if cache_path is not None:
                try:
                    _write_cached_response(cache_path, query, label, merged_response)
                except OSError as error:
                    print(f"  [{label}] cache fusionné non écrit : {str(error)[:80]}")
            return merged_response

    raise RuntimeError(f"Tous les serveurs Overpass ont échoué pour : {label}")
