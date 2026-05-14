# Architecture And Data Contract

## System Shape

```text
scripts/
  build_scenarios.py
        |
        v
data/scenarios/
  risk_050mm.geojson
  risk_100mm.geojson
  risk_150mm.geojson
  risk_200mm.geojson
  risk_250mm.geojson
        |
        v
backend/
  FastAPI scenario service
        |
        v
app/
  Next.js + MapLibre GL JS
```

## Scenario GeoJSON Contract

Each scenario file should be a `FeatureCollection`.

Recommended filename:

```text
data/scenarios/risk_100mm.geojson
```

Feature geometry:

- MVP: grid cell polygon or ward polygon.
- Coordinates: WGS84 `EPSG:4326` for web map compatibility.

Feature properties:

```json
{
  "area_id": "grid_000123",
  "area_name": "Grid 000123",
  "rainfall_mm": 100,
  "risk_score": 72.4,
  "risk_class": "high",
  "base_hazard": 0.68,
  "scenario_hazard": 0.75,
  "runoff_score": 0.82,
  "runoff_mm": 54.1,
  "twi_score": 0.71,
  "water_proximity_score": 0.64,
  "drain_capacity_inverse": 0.58,
  "impervious_score": 0.77,
  "flow_accumulation_score": 0.69,
  "population_exposure_score": 0.62,
  "confidence": "medium"
}
```

## Risk Classes

Use fixed classes for stable colors between rainfall scenarios:

```text
0-20      very_low
20-40     low
40-60     moderate
60-80     high
80-100    severe
```

## API Contract

### `GET /health`

Response:

```json
{
  "status": "ok"
}
```

### `GET /scenarios`

Response:

```json
{
  "rainfall_mm": [50, 100, 150, 200, 250],
  "default": 100,
  "unit": "mm"
}
```

### `GET /risk/{rainfall_mm}`

Returns the scenario GeoJSON for the requested rainfall amount.

Validation:

- Accept only configured rainfall values.
- Return `404` for unsupported values.

## Pipeline Configuration

Keep model assumptions in a versioned config file, for example `config/scoring.yml`:

```yaml
rainfall_scenarios_mm: [50, 100, 150, 200, 250]

weights:
  base_hazard:
    twi_score: 0.35
    water_proximity_score: 0.20
    drain_capacity_inverse: 0.20
    impervious_score: 0.15
    flow_accumulation_score: 0.10
  final:
    scenario_hazard: 0.75
    population_exposure_score: 0.25

curve_number:
  water: 100
  dense_urban: 92
  urban: 85
  open_space: 74
  vegetation: 61
```

## SCS-CN Formula

For rainfall `R` in millimeters:

```text
S = (25400 / CN) - 254
Ia = 0.2 * S

if R <= Ia:
  Q = 0
else:
  Q = (R - Ia)^2 / (R + 0.8 * S)
```

Where:

- `CN` is the curve number.
- `S` is potential maximum retention in millimeters.
- `Ia` is initial abstraction.
- `Q` is direct runoff in millimeters.

## Frontend Layer Contract

MapLibre should style `risk_score` with a fixed expression:

```text
very_low  muted green
low       yellow-green
moderate  yellow
high      orange
severe    red
```

Click inspector should read directly from feature properties. Avoid a second request until the first version is stable.

## Upgrade Path

After MVP:

- Replace GeoJSON with PMTiles or vector tiles for faster rendering.
- Add Cloud Optimized GeoTIFF outputs for raster layers.
- Store vector units and scores in PostGIS.
- Store large static assets in Supabase Storage, S3, or GCS.
- Add calibration against historical flood incidents.
- Add Sentinel-2 land cover classification and NDWI-derived water masks.
- Add model confidence scoring by area.

