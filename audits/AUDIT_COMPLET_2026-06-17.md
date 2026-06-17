# Audit complet — cs2-realmap-generator

Date : 2026-06-17 · Périmètre : dépôt complet (pipeline Python `src/` + `tools/`, visualiseur `visualizer/`, module C# `src/Roads/`, données `exports/`, configuration).
Contrainte respectée : **aucun fichier n'a été modifié**. Ce document est purement analytique.

> Convention de lecture
> **[Fait]** = observé directement dans le code/les données. **[Hypothèse]** = interprétation plausible non prouvée. **[Reco]** = recommandation concrète. Les chemins et numéros de ligne renvoient à l'état actuel du dépôt.

---

## A. Résumé exécutif

`cs2-realmap-generator` est un pipeline cohérent dans son intention : extraire OpenStreetMap via Overpass, classer les objets en zones « Cities: Skylines II », exporter des packs GeoJSON scindés, générer worldmap/heightmap PNG et des manifestes, puis vérifier le tout dans un visualiseur Leaflet. Le cœur Python (`src/`) est **propre, lisible et bien découpé en petites fonctions pures**. La séparation macro (extraction / outils / visualiseur / mod C#) est correcte.

Les faiblesses sont concentrées sur trois axes. **(1) Duplication de logique métier** : la table de correspondance pays→code et la logique de slugification existent en cinq exemplaires divergents (3 Python + 2 JavaScript), et la construction des manifestes est réimplémentée à la fois côté Python et côté JS. **(2) Un fichier frontend hypertrophié** : `visualizer/js/cs2-map-helper.js` (1 522 lignes) concentre génération de commandes, génération de manifestes, création dynamique de DOM, puis masquage immédiat de ce même DOM — symptôme d'indécision produit. **(3) Fiabilité des sorties** : les manifestes générés présents dans `exports/` contiennent des incohérences réelles (nom de fichier heightmap portant la taille du worldmap, bbox worldmap = bbox heightmap, code pays erroné `co` pour Pyongyang). À cela s'ajoutent l'absence totale de tests, des chemins absolus codés en dur à un poste précis, et un risque de fuite de clé API dans les logs.

Le projet est exploitable par son auteur mais **non portable en l'état** et **fragile face à toute évolution** tant que la duplication et le fichier god-object ne sont pas réduits.

## B. Note globale

### **61 / 100**

Bon socle d'extraction, mais dette de duplication, fichier frontend ingérable, incohérences de données générées et absence de tests pèsent fortement.

## C. Notes détaillées

| Domaine | Note /100 | Justification synthétique |
|---|---|---|
| Architecture | 64 | Séparation macro correcte ; minée par duplication inter-fichiers et chemins de données morts. |
| Frontend | 57 | Fonctionnel et accessible, mais god-file de 1 522 lignes + DOM patché à l'exécution. |
| Backend / logique métier | 68 | Cœur Python clair et modulaire ; quelques angles morts de classification et validation. |
| Fiabilité | 54 | Retries Overpass solides, mais sorties générées incohérentes et zéro test. |
| Ergonomie / design | 60 | Navigation géographique soignée ; surcharge fonctionnelle et UI contradictoire. |
| Sécurité | 70 | Surface locale faible ; fuite de clé API en logs et chemins/clés exposés à corriger. |
| SEO / sémantique | N/A | Outil local (localhost), non indexable. Voir section dédiée. |
| Maintenabilité | 52 | Duplication massive, pas de tests, fichiers `.before-*`, deux scripts d'analyse jumeaux. |
| Complexité du code | 58 | `cs2-map-helper.js` et `export_cs2_pngs.main()` très lourds ; reste modéré. |

---

## D. Liste priorisée des problèmes

Chaque entrée : **fichier/module · problème · impact · priorité · recommandation**.

### 🔴 Critique

**D1 — Incohérences dans les manifestes générés** · `tools/write_cs2_bundle_manifest.py` (`build_manifest`, l.95-300) + données `exports/bundles/*/manifest.json`
**[Fait]** Dans `exports/bundles/paris_fr_48.857487_2.352448/manifest.json` : `heightmap.sizeKm = 14.336` mais `paths.heightmapPng = heightmap_2.352_48.857_57.344.png` (taille du **worldmap**) ; et `worldMap.bbox` est **identique** à `heightmap.bbox` alors que les tailles diffèrent (57.344 vs 14.336 km). **Impact** : un consommateur du manifeste (mod C#, futur automate) cherchera un fichier au mauvais nom ou découpera une zone fausse. **Priorité** : critique (corruption silencieuse de contrat). **[Reco]** Recalculer systématiquement `heightmap_bbox` depuis `center+heightmap_km` quand `--heightmap-bbox` n'est pas explicitement différent du worldmap ; ajouter une assertion `worldmap_km != heightmap_km ⇒ world_bbox != heightmap_bbox` et un test de non-régression sur le nom de fichier.

**D2 — Code pays erroné par troncature aveugle** · `visualizer/js/location-navigator.js` (`slugifyCountryCode`, l.122-136) ; `visualizer/js/cs2-map-helper.js` (`resolveCountryCode`, l.130-150) ; `exports/bundles/bundle_index.json`
**[Fait]** Pyongyang est enregistré avec `countryCode: "co"` (dossier `pyongyang_co_...`, `bundle_index.json`). « Corée du Nord » n'est dans aucune table d'alias, donc le fallback `key.slice(0, 2)` de « coree-du-nord » produit `co` — qui est en réalité le code ISO de la Colombie. **Impact** : identifiants de bundle faux, collisions potentielles, étiquetage trompeur dans le catalogue. **Priorité** : critique (donnée fausse, difficilement réversible une fois les dossiers créés). **[Reco]** Supprimer le fallback `slice(0,2)` ; exiger un code ISO-3166 explicite (saisi ou validé contre une liste) et refuser/avertir si absent au lieu d'inventer un code.

**D3 — Cinq définitions divergentes de la table pays→code** · `src/extract_zoning.py` (l.70-82), `tools/export_cs2_pngs.py` (l.12-24), `tools/write_cs2_bundle_manifest.py` (l.11-24), `visualizer/js/cs2-map-helper.js` (l.87-120), `visualizer/js/location-navigator.js` (l.89-110)
**[Fait]** Le même concept (`COUNTRY_CODE_ALIASES`) est dupliqué 5 fois avec des contenus **différents** : la version JS de `cs2-map-helper` couvre ~16 pays, les versions Python 3 pays, `location-navigator` ~10. **Impact** : un même nom de pays produit un code différent selon le composant qui le traite → identifiants de bundle non déterministes entre frontend et backend. **Priorité** : critique pour la cohérence des données. **[Reco]** Source unique de vérité : un fichier `data/country_codes.json` lu par Python et servi/embarqué côté JS. Tant que ce partage n'est pas fait, au minimum aligner les contenus et documenter l'unique table de référence.

### 🟠 Important

**D4 — `cs2-map-helper.js` : god-object de 1 522 lignes** · `visualizer/js/cs2-map-helper.js`
**[Fait]** Ce module mélange : slugification, résolution de code pays, génération de 2 commandes PowerShell, génération de 4 documents JSON (timeline manifest, timeline config, PNG contract, export bundle), création dynamique de sections DOM (`ensureFullBundleCommandUi`, `ensureCs2PngContractUi`, `ensureExportBundleUi`), téléchargements Blob, et hydratation d'état. **Impact** : toute évolution est risquée, la fonction `create()` valide 25+ dépendances DOM (l.1480-1505). **Priorité** : importante (maintenabilité). **[Reco]** Éclater en modules : `bundle-id.js`, `command-builder.js`, `manifest-builder.js`, `helper-ui.js`. Déplacer la génération des manifestes côté backend (voir D7) pour supprimer la moitié du fichier.

**D5 — DOM construit puis masqué/réécrit à l'exécution (UI contradictoire)** · `visualizer/js/cs2-map-helper.js` (`normalizeInformationPanel` l.856-888, `hideBackendHelperBlocks` l.890-913, appelées dans `update` l.966 & 997)
**[Fait]** Le code crée des blocs (commande bundle, contrat PNG, export bundle) via `ensure*Ui`, puis `hideBackendHelperBlocks` masque/supprime des blocs voisins ; `normalizeInformationPanel` renomme à l'exécution un titre « Aide CS2 » en « Informations » alors que `index.html` (l.101) affiche déjà « Informations », et masque les libellés « Pas N m » par expression régulière. **Impact** : indécision produit gelée dans le code, surcoût DOM, comportement difficile à prédire, **[Hypothèse]** vestiges de refontes successives jamais nettoyées. **Priorité** : importante. **[Reco]** Décider de l'état final de chaque bloc, le refléter directement dans `index.html`/CSS, et supprimer le patching runtime (`normalizeInformationPanel`, `hideBackendHelperBlocks`).

**D6 — Chemins absolus codés en dur sur un poste précis** · `visualizer/js/cs2-map-helper.js` (l.286-287, 302-303, 371-372)
**[Fait]** Les commandes générées contiennent `C:\\Python314\\python.exe` et `C:\\Users\\cadet\\Documents\\GitHub\\cs2-realmap-generator\\...`. **Impact** : l'outil n'est utilisable que par l'auteur ; tout autre utilisateur (ou un déplacement du dépôt) casse les commandes copiées. Fuite mineure du nom d'utilisateur. **Priorité** : importante (portabilité). **[Reco]** Générer des commandes relatives (`python`, `.\src\extract_zoning.py`) ou rendre le préfixe configurable (champ UI / paramètre injecté au chargement de la page).

**D7 — Double implémentation de la génération de manifestes (Python ⇄ JS)** · `tools/write_cs2_bundle_manifest.py` (`build_manifest`) vs `visualizer/js/cs2-map-helper.js` (`buildTimelineManifest` l.482, `buildExportBundleManifest` l.632, `buildCs2PngContract` l.335)
**[Fait]** Le frontend recompose des manifestes/contrats JSON dont la version 2 « officielle » est aussi produite par le Python. Les deux peuvent diverger (ex. `version:1` côté JS vs `version:2` côté Python observé dans `exports/`). **Impact** : deux sources de vérité pour le même artefact → dérive garantie. **Priorité** : importante. **[Reco]** Le frontend ne devrait produire que la **commande** ; les fichiers JSON doivent être générés exclusivement par le backend. Supprimer la génération de manifestes/contrats du JS.

**D8 — Fuite potentielle de la clé API dans les logs** · `tools/export_terrain_rgb_png.py` (`build_tile_url` l.56-63 injecte la clé en query string ; `fetch_bytes` l.81 `print(... {exc})`)
**[Fait]** La clé MapTiler/Mapbox est placée dans l'URL (`?key=...`). En cas d'erreur HTTP, `urllib` inclut souvent l'URL dans le message d'exception, qui est imprimé tel quel. **Impact** : la clé peut se retrouver en clair dans la console/les logs partagés. **Priorité** : importante (sécurité, niveau moyen-élevé). **[Reco]** Avant impression, masquer la query string (`re.sub(r"(key|access_token)=[^&]+", r"\1=***", str(exc))`). Préférer, si l'API le permet, l'envoi de la clé en en-tête plutôt qu'en URL.

**D9 — Aucun test automatisé** · ensemble du dépôt
**[Fait]** Aucun fichier `test_*.py` / `*.test.js`. **Impact** : les fonctions à logique sensible (slugify, `resolveCountryCode`, `bbox_text_from_center_size`, classification, conversion lat/lon↔lon/lat) ne sont protégées par aucun garde-fou ; les bugs D1/D2 seraient détectés par un seul test. **Priorité** : importante. **[Reco]** Ajouter `pytest` ciblant en priorité : génération d'id de bundle (déterminisme Py vs JS), cohérence bbox worldmap≠heightmap, classification résidentielle/commerciale sur cas types, round-trip de coordonnées.

**D10 — Dépendances non déclarées** · `src/pyproject.toml` (l.5-8)
**[Fait]** `pyproject.toml` ne déclare que `requests` et `tqdm`, mais `tools/` importe `numpy`, `Pillow`, `shapely` (cf. `export_terrain_rgb_png.py`, `export_heightmap_from_dem.py`, `clip_*`). Le README demande de les installer à la main. **Impact** : `uv sync` ne suffit pas à faire tourner les outils ; mise en route fragile. **Priorité** : importante. **[Reco]** Déclarer les dépendances des outils (groupe optionnel `[project.optional-dependencies] tools = ["numpy","pillow","shapely"]`). Vérifier aussi que `tqdm` est réellement utilisé.

### 🟡 Moyen

**D11 — Déduplication `office` partielle** · `src/extract_zoning.py` (l.861-863)
**[Fait]** Les éléments `office` déjà présents dans `commercial` sont ignorés (`commercial_ids`), mais aucune déduplication équivalente n'existe entre `office`/`industrial`/`retail`/`mixed` qui peuvent se recouvrir (un même way `landuse` taggé multiple). **Impact** : double comptage possible d'un même polygone sur deux couches. **Priorité** : moyenne. **[Reco]** Centraliser une déduplication par `id` à travers toutes les catégories de polygones, ou documenter explicitement que les recouvrements sont assumés.

**D12 — Absence de validation des bornes/ordre de la bbox** · `src/extract_zoning.py` (`bbox_center_lon_lat` l.133-139)
**[Fait]** La bbox est seulement découpée en 4 floats ; aucun contrôle que `south < north`, `west < east`, ou que les valeurs sont dans [-90,90]/[-180,180]. **Impact** : une bbox inversée passe silencieusement et renvoie une zone vide ou aberrante d'Overpass après une longue attente. **Priorité** : moyenne. **[Reco]** Valider l'ordre et les bornes, lever une `SystemExit` explicite avec message.

**D13 — Deux scripts d'analyse jumeaux** · `tools/analyze_zoning_data.py` (376 l.) et `tools/analyze_zoning_data_v2.py` (316 l.)
**[Fait]** Deux variantes coexistent (la v2 ajoute `import re`, supprime `INTERESTING_KEYS`, etc.). **[Hypothèse]** v2 remplace v1. **Impact** : ambiguïté sur le script de référence, maintenance dédoublée. **Priorité** : moyenne. **[Reco]** Confirmer le script vivant, archiver/supprimer l'autre (hors de `tools/`).

**D14 — Chemin de données « legacy » mort** · `visualizer/js/config.js` (`globalName: DATA_*`), `visualizer/js/data-adapter.js` (`SOURCE_READERS` l.4-32), `.gitignore` (l.18 `visualizer/zoning_data.js`)
**[Fait]** Tout un chemin de lecture via variables globales `DATA_RESIDENTIAL`… subsiste, mais `index.html` ne charge aucun `zoning_data.js` (seul le mode `pack` via `fetch` est câblé). `dataMode: "legacy"` n'est jamais réellement emprunté avec données. **Impact** : code mort entretenant l'illusion de deux modes. **Priorité** : moyenne. **[Reco]** Supprimer `SOURCE_READERS`/`globalName` et le mode legacy, ou le documenter comme déprécié.

**D15 — Clé garbled dans la liste de clés de contrat** · `tools/export_cs2_pngs.py` (l.252)
**[Fait]** `["centerLon", "center_lون", "center_lon", "lon", "longitude"]` contient une clé corrompue `center_lون` (caractères arabes). Inoffensive (ne matche jamais) mais révélatrice d'une corruption d'édition. **Impact** : bruit, signe de copier-coller hasardeux. **Priorité** : moyenne (qualité). **[Reco]** Supprimer la clé corrompue.

**D16 — `packIndexPath` lu depuis l'URL sans contrôle** · `visualizer/js/app.js` (`getExplicitPackIndexPath` l.34-48), `pack-loader.js` (`loadDefaultPack`)
**[Fait]** Le paramètre d'URL `packIndexPath` est passé tel quel à `fetch`. Contexte = serveur local statique. **Impact** : faible en local, mais permet de charger un chemin arbitraire accessible par le serveur (lecture seule). **Priorité** : moyenne. **[Reco]** Restreindre le préfixe accepté à `../exports/bundles/` et rejeter les chemins hors arborescence.

### 🟢 Mineur

**D17 — Constante morte** · `visualizer/js/cs2-overlay-controller.js` (l.4) : `EARTH_METERS_PER_DEGREE = 111320` jamais utilisée (la fonction précise `metersPerDegree` est employée). **[Reco]** Supprimer.

**D18 — Fichiers de sauvegarde versionnables dans `src/`** · `src/extract_zoning.py.before-args-fix`, `.before-official-exports-pack`, `.before-official-pack`, `.before-split-layers`, `.before-water-layers` **[Fait]** présents sur disque (non suivis par git). **Impact** : pollution du dossier source, confusion. **[Reco]** Déplacer ces sauvegardes hors `src/` (dossier `no_push/` déjà prévu par `.gitignore`).

**D19 — `__pycache__` présents dans `src/` et `tools/`** · non suivis (gitignore OK) mais présents physiquement. **[Reco]** Nettoyage ponctuel.

**D20 — `safe-html.js` sous-utilisé** · `visualizer/js/safe-html.js` n'est consommé que par `map-controller.js`. Les autres rendus passent par `textContent`/`createElement` (sûrs), mais `bundle-catalog-controller.js` (l.284) utilise `innerHTML = ""` (vidage, inoffensif). **[Reco]** Garder la convention `escapeHTML` documentée pour toute future insertion HTML ; remplacer le `innerHTML=""` par `replaceChildren()` pour cohérence.

**D21 — Incohérences de style mineures** · indentation mêlant tabulations et espaces dans `index.html` (l.67, 188-194) et `bundle-catalog-controller.js` (l.254, 390) ; `roundNumber` utilisé avant sa déclaration dans `cs2-map-helper.js` (hoisting OK mais déroutant). **[Reco]** Passer un formateur (Prettier/Black) en CI.

---

## E. Contradictions et incohérences détectées

1. **[Fait]** *Données générées contradictoires* — manifeste Paris : `heightmap.sizeKm=14.336` mais nom de fichier heightmap en `57.344` ; `worldMap.bbox == heightmap.bbox` (cf. D1).
2. **[Fait]** *Code pays inventé* — Pyongyang → `co` au lieu de `kp` (cf. D2).
3. **[Fait]** *Déterminisme rompu* — 5 tables `COUNTRY_CODE_ALIASES` divergentes : un même pays peut produire deux id de bundle différents selon le composant (cf. D3).
4. **[Fait]** *Double vérité des manifestes* — Python (version 2) et JS (version 1) produisent des structures concurrentes (cf. D7).
5. **[Fait]** *UI construite puis annulée* — blocs DOM créés par `ensure*Ui` puis masqués/supprimés par `hideBackendHelperBlocks`, titre réécrit à l'exécution alors que le HTML est déjà à jour (cf. D5).
6. **[Fait]** *Précision incohérente du centre* — `center` arrondi à 3 décimales dans le manifeste (`2.352`, `48.857`) alors que l'id de bundle conserve 6 décimales (`2.352448`, `48.857487`) ; le rapprochement « bundle cible ↔ bundle local » repose d'ailleurs sur une tolérance de 1 km (`bundle-catalog-controller.js` l.244) pour compenser cet écart — contournement plutôt que correction.
7. **[Fait]** *Deux modèles d'initialisation frontend* — `app.js` orchestre `MapController/Panel/Overlay/Helper`, tandis que `location-navigator.js` et `bundle-catalog-controller.js` s'auto-initialisent sur `DOMContentLoaded` et que `location-navigator` **sonde** `App.state.mapController` par polling (`waitForMap`, l.316-334). Architecture d'amorçage hybride.
8. **[Fait]** *README vs réalité* — le README décrit un mode visualiseur chargeant les GeoJSON par `fetch` ; le mode `legacy` par variables globales reste pourtant câblé dans `config.js`/`data-adapter.js` sans être atteignable (cf. D14).
9. **[Fait]** *`pyproject` vs dépendances réelles* — outils nécessitant numpy/pillow/shapely non déclarés (cf. D10).

---

## F. Fonctionnalités à conserver

- **Pipeline d'extraction Overpass** (`src/extract_zoning.py`, `overpass_client.py`, `cs2_zones.py`) : requêtes séparées par catégorie, rotation de 4 serveurs, backoff exponentiel, messages console clairs. **[Fait]** robuste et bien écrit.
- **Classification CS2** (`src/classifiers.py`) : logique simple, lisible, honnêtement documentée comme heuristique (résidentiel haut/moyen/bas, parking ouvrage/surface, familles de routes). À garder.
- **Pack GeoJSON scindé par couche + rapports** (`write_split_layers_pack`) : structure claire (`geojson/`, `reports/layer_index.json`, `extraction_report.json`), conversion lat/lon→lon/lon correcte.
- **Module C# Roads** (`src/Roads/*.cs`) : petit, lisible, bien typé (`RoadImportMetadata`, `RoadPrefabResolver`, `RuntimeRoadSpawner`). Bon découpage métadonnées/résolution/spawn.
- **Navigation géographique** (`location-navigator.js`) : continent → pays → capitale, validation de points/bounds, `animate:false`. UX nette.
- **Overlay CS2 worldmap/heightmap** (`cs2-overlay-controller.js`) : calcul `metersPerDegree` précis, nudges N/S/E/O, snapshot/observateurs propres.
- **Sécurité des popups** (`map-controller.js` + `safe-html.js`) : échappement systématique, limite de 12 tags. Bonne pratique à généraliser.

## G. Fonctionnalités à refaire (refonte)

- **Génération d'id de bundle et résolution de code pays** : unifier en une source unique partagée Py/JS (D2, D3).
- **Génération des manifestes/contrats** : recentrer côté backend uniquement ; le frontend ne produit que la commande (D7).
- **`cs2-map-helper.js`** : éclatement en modules + suppression du DOM patché à l'exécution (D4, D5).
- **Génération des commandes** : rendre relative/configurable (D6).
- **Amorçage frontend** : un orchestrateur unique dans `app.js` injectant `locationNavigator` et `bundleCatalog` au lieu du polling/auto-init (incohérence E7).

## H. Fonctionnalités à retirer

- **Mode de données « legacy »** par variables globales `DATA_*` (`config.js`, `data-adapter.js`) — non atteignable (D14).
- **Constante `EARTH_METERS_PER_DEGREE`** morte (D17).
- **`normalizeInformationPanel` / `hideBackendHelperBlocks`** une fois l'UI figée dans le HTML (D5).
- **Script d'analyse redondant** parmi `analyze_zoning_data.py` / `_v2.py` (D13).
- **Fichiers `*.before-*`** de `src/` (D18) et `__pycache__` (D19).
- **Bloc de génération de manifeste JSON côté JS** après bascule sur backend (D7).

## I. Proposition de refactorisation (sans modifier les fichiers)

1. **Source unique des correspondances pays** : créer `data/country_codes.json` (nom→code ISO + alias FR/EN), lu par les 3 scripts Python et embarqué/servi pour les 2 modules JS. Supprime D3 et D2 d'un coup.
2. **Bibliothèque partagée d'identité de bundle** : factoriser `slugify`/`sanitize_bundle_id`/`build_bundle_id` dans un seul module Python (`src/bundle_identity.py`) importé par `extract_zoning`, `export_cs2_pngs`, `write_cs2_bundle_manifest` ; côté JS, un seul `bundle-id.js`. Documenter le contrat « ville_pays_lat6_lon6 » comme unique.
3. **Backend = seul producteur d'artefacts JSON** : retirer du frontend `buildTimelineManifest`, `buildExportBundleManifest`, `buildCs2PngContract` ; ne conserver que `buildCommand`/`buildFullBundleCommand`, rendues relatives.
4. **Découper `cs2-map-helper.js`** en `bundle-id.js`, `command-builder.js`, `helper-ui.js` ; faire que `create()` échoue proprement (log) plutôt que renvoyer `null` après 25 vérifications.
5. **Invariants explicites côté `write_cs2_bundle_manifest`** : asserts `world_bbox != heightmap_bbox` quand les tailles diffèrent, nom de fichier heightmap = taille heightmap. Couvre D1.
6. **Validation des entrées** : bbox (ordre/bornes) dans `extract_zoning`, restriction de `packIndexPath` au préfixe `exports/bundles/` côté visualiseur (D12, D16).
7. **Masquage des secrets dans les logs** : helper `redact(url|exc)` dans `export_terrain_rgb_png` (D8).
8. **Harnais de tests `pytest`** + un petit jeu JS (ou tests Node) sur slugify/code pays pour garantir la parité Py/JS (D9).
9. **Déclarer les dépendances outils** dans `pyproject.toml` (D10).

## J. Proposition d'arborescence plus cohérente

**[Reco]** — cible indicative, non appliquée :

```
cs2-realmap-generator/
├─ data/
│  └─ country_codes.json          # source unique (remplace 5 tables)
├─ pipeline/                       # ex-"src/", logique métier d'extraction
│  ├─ extract_zoning.py
│  ├─ classifiers.py
│  ├─ cs2_zones.py
│  ├─ overpass_client.py
│  └─ bundle_identity.py           # slugify/build_bundle_id factorisés
├─ tools/                          # outils PNG/heightmap/manifest/validation
│  ├─ export_cs2_pngs.py
│  ├─ export_terrain_rgb_png.py
│  ├─ export_heightmap_from_dem.py
│  ├─ write_cs2_bundle_manifest.py
│  ├─ validate_png_contract.py
│  └─ analyze_zoning_data.py       # un seul (v1/v2 fusionnés)
├─ mod/                            # ex-"src/Roads/", code C# du jeu
│  └─ Roads/*.cs
├─ visualizer/
│  ├─ index.html
│  ├─ styles/ (tokens.css, app.css)
│  └─ js/
│     ├─ core/        (config, data-adapter, pack-loader, stats)
│     ├─ map/         (map-controller, cs2-overlay-controller, safe-html)
│     ├─ panels/      (panel-controller, location-navigator, bundle-catalog-controller)
│     └─ helper/      (bundle-id, command-builder, helper-ui)   # ex cs2-map-helper éclaté
├─ tests/             (pytest + parité Py/JS)
├─ exports/           (généré, déjà gitignoré)
├─ docs/  ·  audits/
├─ pyproject.toml  ·  README.md  ·  LICENSE
└─ no_push/           (sauvegardes *.before-*, déjà gitignoré)
```

Points clés : séparer nettement **logique métier** (`pipeline/`), **outillage** (`tools/`), **code du jeu** (`mod/`) et **données de référence** (`data/`) ; sortir le mod C# de `src/` (il n'est pas du Python) ; sortir les sauvegardes hors source.

## K. Plan d'action recommandé (par ordre d'importance)

1. **Corriger les incohérences de manifeste** (D1) — invariants + recalcul bbox/nom de fichier heightmap. *Bloque la fiabilité des sorties.*
2. **Fiabiliser les codes pays** (D2) — supprimer le fallback `slice(0,2)`, exiger un code ISO validé.
3. **Unifier pays→code et identité de bundle** (D3, refacto I.1/I.2) — source unique Py/JS.
4. **Ajouter des tests** sur slugify, code pays, bbox, classification (D9) — pour figer 1-3.
5. **Recentrer la génération JSON côté backend** (D7) et **rendre les commandes portables** (D6).
6. **Masquer la clé API dans les logs** (D8) et **restreindre `packIndexPath`** (D16).
7. **Éclater `cs2-map-helper.js`** et **supprimer le DOM patché à l'exécution** (D4, D5).
8. **Déclarer les dépendances outils** (D10), **valider la bbox** (D12).
9. **Nettoyage** : mode legacy mort (D14), constante morte (D17), scripts jumeaux (D13), fichiers `.before-*`/`__pycache__` (D18-D19), clé garbled (D15), style (D21).

---

## Annexe — SEO et sémantique

**[Fait] SEO non applicable.** Le visualiseur est une application servie en local (`python -m http.server`, `http://localhost:8000/visualizer/`), non destinée à l'indexation publique. Aucun objectif de référencement n'est pertinent ici. Forcer une analyse SEO (sitemap, balises OpenGraph, robots.txt) serait hors-sujet.

**Sémantique / accessibilité HTML (utile, lui) :** `index.html` est correct — `lang="fr"`, `charset`, `viewport`, repères ARIA (`aria-label`, `aria-live`, `role="alert"`), structure `main/nav/aside/section/header` cohérente, `<label for>` reliés aux contrôles. Manques mineurs : pas de hiérarchie de titres unique pour un document (plusieurs `h2` sans `h1` de page hors en-tête — acceptable pour un dashboard), `<meta name="description">` absent (sans impact en local). **[Reco]** conserver la rigueur ARIA actuelle ; aucune action SEO requise.

---

*Rapport généré sans aucune modification des fichiers du projet. Les éléments de `exports/` cités sont des artefacts générés localement (dossier gitignoré) et reflètent une exécution réelle du pipeline.*
