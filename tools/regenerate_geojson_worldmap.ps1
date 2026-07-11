# Regeneration des packs GeoJSON sur la bbox worldmap (57,344 km)
# Principe « bundle Paris » : l'extraction GeoJSON couvre TOUJOURS la bbox worldmap,
# jamais la bbox heightmap (14,336 km). Paris est deja conforme et n'est pas relance.
# Lancer depuis la racine du depot : .\tools\regenerate_geojson_worldmap.ps1

if (-not (Test-Path '.\src\extract_zoning.py')) { throw 'Lance ce script depuis la racine du depot cs2-realmap-generator.' }

Write-Host 'Extraction Irvine (us) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Irvine" `
  --country "United States" `
  --country-code "us" `
  --bbox "33.394993,-118.033104,33.911997,-117.414894" `
  --bundle-output `
  --bundle-id "irvine_ca_us_33.653495_-117.723999" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction irvine_ca_us_33.653495_-117.723999' }

Write-Host 'Extraction Jakarta (id) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Jakarta" `
  --country "Indonésie" `
  --country-code "id" `
  --bbox "-6.467334,106.585926,-5.948793,107.104074" `
  --bundle-output `
  --bundle-id "jakarta_id_-6.208064_106.845000" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction jakarta_id_-6.208064_106.845000' }

Write-Host 'Extraction Jérusalem (il) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Jérusalem" `
  --country "Israël" `
  --country-code "il" `
  --bbox "31.509421,34.911330,32.026579,35.516670" `
  --bundle-output `
  --bundle-id "jerusalem_il_31.768000_35.214000" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction jerusalem_il_31.768000_35.214000' }

Write-Host 'Extraction Lisbonne (pt) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Lisbonne" `
  --country "Portugal" `
  --country-code "pt" `
  --bbox "38.463717,-9.468698,38.980283,-8.809302" `
  --bundle-output `
  --bundle-id "lisbonne_pt_38.722000_-9.139000" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction lisbonne_pt_38.722000_-9.139000' }

Write-Host 'Extraction Ouagadougou (bf) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Ouagadougou" `
  --country "Burkina Faso" `
  --country-code "bf" `
  --bbox "12.111819,-1.782647,12.630181,-1.255353" `
  --bundle-output `
  --bundle-id "ouagadougou_bf_12.371000_-1.519000" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction ouagadougou_bf_12.371000_-1.519000' }

Write-Host 'Extraction Prague (cz) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Prague" `
  --country "Tchéquie" `
  --country-code "cz" `
  --bbox "49.818320,14.037550,50.333862,14.838640" `
  --bundle-output `
  --bundle-id "prague_cz_50.076091_14.438095" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction prague_cz_50.076091_14.438095' }

Write-Host 'Extraction Pyongyang (kp) sur bbox worldmap 57,344 km...' -ForegroundColor Cyan
& python .\src\extract_zoning.py `
  --city "Pyongyang" `
  --country "Corée du Nord" `
  --country-code "kp" `
  --bbox "38.780731,125.430833,39.297269,126.093167" `
  --bundle-output `
  --bundle-id "pyongyang_co_39.039000_125.762000" `
  --split-layers
if ($LASTEXITCODE -ne 0) { throw 'Echec extraction pyongyang_co_39.039000_125.762000' }

# Synchronisation vers CityTimelineMod
$timelineBundles = "$env:USERPROFILE\AppData\LocalLow\Colossal Order\Cities Skylines II\Mods\CityTimelineMod\data\exports\bundles"
New-Item -ItemType Directory -Force $timelineBundles | Out-Null
Copy-Item '.\exports\bundles\bundle_index.json' "$timelineBundles\bundle_index.json" -Force
Copy-Item '.\exports\bundles\irvine_ca_us_33.653495_-117.723999' "$timelineBundles\irvine_ca_us_33.653495_-117.723999" -Recurse -Force
Copy-Item '.\exports\bundles\jakarta_id_-6.208064_106.845000' "$timelineBundles\jakarta_id_-6.208064_106.845000" -Recurse -Force
Copy-Item '.\exports\bundles\jerusalem_il_31.768000_35.214000' "$timelineBundles\jerusalem_il_31.768000_35.214000" -Recurse -Force
Copy-Item '.\exports\bundles\lisbonne_pt_38.722000_-9.139000' "$timelineBundles\lisbonne_pt_38.722000_-9.139000" -Recurse -Force
Copy-Item '.\exports\bundles\ouagadougou_bf_12.371000_-1.519000' "$timelineBundles\ouagadougou_bf_12.371000_-1.519000" -Recurse -Force
Copy-Item '.\exports\bundles\prague_cz_50.076091_14.438095' "$timelineBundles\prague_cz_50.076091_14.438095" -Recurse -Force
Copy-Item '.\exports\bundles\pyongyang_co_39.039000_125.762000' "$timelineBundles\pyongyang_co_39.039000_125.762000" -Recurse -Force
Write-Host 'Tous les packs GeoJSON regeneres sur la bbox worldmap.' -ForegroundColor Green
