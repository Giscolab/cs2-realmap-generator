# Convention de couleurs partagée — CityTimelineMod ↔ cs2-realmap-generator

**Source unique de vérité : cs2-realmap-generator** (`src/road_categories.py` pour les routes, `visualizer/js/config.js` pour le zonage et l'eau). CityTimelineMod traduit ces hex en noms français dans `src/CityTimelineMod/Config/GeoOverlayConfig.Colors.cs`. Toute modification de couleur doit partir du realmap, puis être répercutée ici.

Une copie de ce document existe dans les deux dépôts (`docs/color-conventions.md`). Les deux copies doivent rester identiques.

## Routes

| Catégorie realmap | Hex | Nom CityTimelineMod | Clé config |
|---|---|---|---|
| highway (motorway, trunk) | `#ff4d4d` | `rouge` | `roadColorMotorway` |
| large_road (primary) | `#ff9f1c` | `orange` | `roadColorPrimary` |
| medium_road (secondary) | `#ffd60a` | `jaune` | `roadColorSecondary` |
| small_road (tertiary, residential) | `#ffffff` | `blanc` | `roadColorTertiary` |
| ramp (*_link) | `#ff3df5` | `magenta` | `roadColorLink` |
| pathway (piéton, cycle) | `#2ad4ff` | `cyan` | `pathColor` |
| gravel_road (non classée) | `#c7d0d9` | `grisClair` | `roadColorDefault` |

## Eau

| Couche realmap | Hex | Nom CityTimelineMod | Clé config |
|---|---|---|---|
| Lignes d'eau | `#38bdf8` | `bleuClair` | `waterLineColor` |
| Surfaces d'eau (remplissage) | `#0ea5e9` | `bleu` | `waterAreaFillColor` |
| Surfaces d'eau (contour) | `#0284c7` | `bleuFonce` | `waterAreaOutlineColor` |

## Zonage

| Couche realmap | Hex | Nom CityTimelineMod | Clé config |
|---|---|---|---|
| res_low | `#7ab64d` | `vertClair` | `zoningResidentialLowColor` |
| res_med | `#2d9d54` | `vertMoyen` | `zoningResidentialMediumColor` |
| res_high | `#0b6f3a` | `vertFonce` | `zoningResidentialHighColor` |
| com_low | `#4aa3ff` | `bleuCommercialClair` | `zoningCommercialLowColor` |
| com_high | `#1f57d6` | `bleuCommercial` | `zoningCommercialHighColor` |
| retail | `#74c5ff` | `bleuDetail` | `zoningRetailColor` |
| industrial | `#d6ad32` | `ambre` | `zoningIndustrialColor` |
| office | `#a46bd5` | `violet` | `zoningOfficeColor` |
| prk_surface | `#b9ed70` | `vertParkingClair` | `zoningSurfaceColor` |
| prk_ramp | `#5fe86e` | `vertParking` | `zoningRampColor` |
| mixed | `#2ed6e5` | `turquoise` | `zoningMixedColor` |
| (inconnu) | — | `blanc` | `zoningFallbackColor` |

## Règles

1. Ne jamais modifier une couleur d'un seul côté. On change d'abord le realmap, puis `GeoOverlayConfig.Colors.cs`, puis ce document (dans les deux dépôts).
2. Les noms de couleurs du mod sont normalisés (minuscules, sans accents, sans tirets/underscores) par `NormalizeColorName` : les `case` du switch doivent donc être entièrement en minuscules.
3. Le mapping label CS2 → matériau de zonage vit dans `ZoningMaterialResolver.cs`. Chaque `cs2:` du `visualizer/js/config.js` du realmap doit avoir une entrée correspondante.

## Historique

- 2026-07-12 : alignement complet du mod sur la palette realmap ; ajout de `commercial_high` et `mixed` ; correction de l'ordre des matériaux passés à `RenderZoningFillMeshes` (industrial/commercial/retail étaient permutés) ; correction du `case "vertMoyen"` jamais atteint.
