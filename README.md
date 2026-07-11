<div align="center">

# CS2 Realmap Generator
## Pipeline OpenStreetMap -> Cities: Skylines II

> Extraction Overpass, classification CS2, pack GeoJSON scindé, PNG worldmap/heightmap et manifests pour un workflow Cities: Skylines II / CityTimelineMod.
>

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Licence MIT](https://img.shields.io/badge/Licence-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Données OSM](https://img.shields.io/badge/Donn%C3%A9es-OpenStreetMap-7B3F00?style=for-the-badge&logo=openstreetmap)](https://www.openstreetmap.org/)
[![Leaflet](https://img.shields.io/badge/Visualiseur-Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com/)

</div>

---

## Aperçu

<div align="center">

| Carte interactive complète | Zoom centre-ville |
|:---:|:---:|
| ![Aperçu complet](docs/screenshots/preview_full.png) | ![Zoom centre-ville](docs/screenshots/preview_downtown.png) |
| Visualiseur Leaflet des objets OSM classés | Exemple de rendu avec couches de densité visibles |

</div>

---

## Objectif du projet

`cs2-realmap-generator` transforme une emprise géographique réelle en ressources utilisables pour préparer une carte Cities: Skylines II.

Le projet sert à générer des bundles contenant notamment :

- des couches GeoJSON extraites depuis OpenStreetMap ;
- des routes, chemins, surfaces d’eau, lignes d’eau et zones d’usage ;
- des couches de services en points (9 familles : éducation, incendie, médical, parcs, électricité, déchets, transport, eau, communications) ;
- des PNG `worldmap` et `heightmap` compatibles avec le workflow CS2 ;
- un `manifest.json` décrivant le bundle ;
- un `timeline_config.json` utilisable par CityTimelineMod ;
- un `bundle_index.json` listant les bundles générés ;
- un visualiseur Leaflet pour vérifier les données avant usage dans le jeu.

Le projet ne fournit pas un zonage administratif officiel. Il produit une interprétation technique, vérifiable et exploitable des données OpenStreetMap disponibles.

---

## Installation

Prérequis :

- Python 3.11 ou plus récent ;
- navigateur moderne pour le visualiseur ;
- connexion réseau pour Overpass, les tuiles Leaflet/CARTO et Terrain RGB ;
- une clé `MAPTILER_API_KEY` ou `MAPBOX_TOKEN` pour les PNG terrain.

Depuis la racine du dépôt :

```powershell
cd src
uv sync
cd ..
```

Sans `uv` :

```powershell
python -m pip install requests tqdm
```

Pour les outils PNG et de clipping :

```powershell
python -m pip install numpy pillow shapely
```

Avant un export Terrain RGB MapTiler :

```powershell
$env:MAPTILER_API_KEY = "votre-cle"
```

Ou avec Mapbox :

```powershell
$env:MAPBOX_TOKEN = "votre-token"
```


## Ouvrir le visualiseur

Le visualiseur charge les GeoJSON avec `fetch` ; il doit donc être servi en HTTP local depuis la racine du dépôt :

```powershell
python -m http.server 8000
```

Puis ouvrez :

```text
http://localhost:8000/visualizer/
```

## Limites connues

- La qualité dépend directement des tags OpenStreetMap.
- `building:levels` est souvent incomplet ; la densité résidentielle peut rester basse par défaut.
- Overpass peut être lent ou échouer sur de grandes emprises. Le pipeline réduit le risque avec des requêtes séparées et une rotation de serveurs, sans le supprimer.
- Les exports Terrain RGB nécessitent un fournisseur externe, une clé API et une connexion réseau.
- Les services sont extraits en points (centroïdes) : pas d'emprises surfaciques ni de réseaux (égouts, canalisations) dans le pipeline courant.
- Le projet prépare des ressources et contrats ; l'intégration finale côté jeu ou mod reste une étape séparée.

---

## Licence

MIT - voir [LICENSE](LICENSE).

Donnees cartographiques © contributeurs [OpenStreetMap](https://www.openstreetmap.org/), sous licence [ODbL](https://www.openstreetmap.org/copyright).
