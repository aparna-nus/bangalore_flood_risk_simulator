# MVP Roadmap

## Product Thesis

The MVP should demonstrate a credible geospatial risk workflow, not a perfect hydrological model. The strongest portfolio story is:

> I can ingest real geospatial datasets, derive explainable risk features, simulate rainfall scenarios, and expose the result through a polished interactive map.

## Scope

### In

- Bangalore study area boundary.
- DEM-derived slope, flow direction, flow accumulation, and approximate topographic wetness index.
- OSM-derived water bodies, waterways, road density, building density, and approximate drainage availability.
- SCS Curve Number runoff estimate for fixed rainfall depths.
- Composite risk and exposure score.
- Precomputed scenario GeoJSON files.
- FastAPI endpoint for scenario metadata and GeoJSON.
- MapLibre frontend with rainfall slider, legend, and click inspector.

### Out For MVP

- Real-time hydrodynamic simulation.
- Drain pipe hydraulic capacity modeling.
- ML flood prediction unless reliable labels are available.
- Full PostGIS/S3/Supabase deployment on day one.
- Citywide 10m Cartosat pipeline if data access becomes slow or manual.

## MVP Build Phases

### Phase 0: Project Skeleton

Purpose: make the repo navigable and explainable.

Deliverables:

- `README.md`
- `docs/mvp-roadmap.md`
- `docs/architecture.md`
- Placeholder folders for `backend`, `app`, `scripts`, `data`, and `notebooks`.

### Phase 1: Data Acquisition

Preferred MVP sources:

- Study area: BBMP ward boundaries if available, otherwise a Bangalore bounding box.
- DEM: Copernicus DEM 30m first; Cartosat-1 10m documented as a quality upgrade.
- OSM: use `osmnx` or `osmium`/Geofabrik extract for roads, waterways, water bodies, buildings, and drainage-like features.
- Population: WorldPop or GHSL population grid, optional in first pass.
- Land cover: start with a simple proxy from OSM/building/road density; add Sentinel-2 classification later.

Why this order:

- Copernicus + OSM gets the full product loop working quickly.
- Cartosat and Sentinel improve scientific quality, but they can add access friction.
- A working scenario map beats a perfect offline notebook.

### Phase 2: Processing Pipeline

Create `scripts/build_scenarios.py` with stages that can be run independently:

1. Load study boundary and reproject to a metric CRS.
2. Clip DEM to Bangalore.
3. Fill sinks or apply a simple depression handling method.
4. Compute slope, flow direction, and flow accumulation.
5. Estimate TWI as `ln(flow_accumulation / tan(slope))`.
6. Extract OSM-derived feature layers.
7. Derive normalized feature rasters or grid attributes:
   - `twi_score`
   - `water_proximity_score`
   - `drain_capacity_inverse`
   - `impervious_score`
   - `population_exposure_score`
8. For each rainfall depth, estimate runoff with SCS-CN.
9. Route runoff approximately using flow accumulation as a multiplier.
10. Aggregate to ward polygons or hex/grid cells.
11. Write `data/scenarios/risk_050mm.geojson`, etc.

### Phase 3: Scoring Model

Use a transparent weighted model first.

Baseline static hazard:

```text
BaseHazard =
  0.35 * twi_score +
  0.20 * water_proximity_score +
  0.20 * drain_capacity_inverse +
  0.15 * impervious_score +
  0.10 * flow_accumulation_score
```

Rainfall scenario modifier:

```text
ScenarioHazard =
  0.60 * BaseHazard +
  0.40 * runoff_accumulation_score
```

Final risk:

```text
RiskScore =
  0.75 * ScenarioHazard +
  0.25 * population_exposure_score
```

All component scores should be normalized to `0..1`, then `RiskScore` can be exposed as both `0..1` and `0..100`.

### Phase 4: Backend

Start small with FastAPI:

- `GET /health`
- `GET /scenarios`
- `GET /risk/{rainfall_mm}`
- `GET /areas/{area_id}` if detailed breakdowns are split later

The backend can read local files from `data/scenarios` for MVP. Supabase Storage, S3, COGs, and PostGIS can be added after the UI and scoring loop work locally.

### Phase 5: Frontend

Use Next.js + MapLibre GL JS.

Core screens:

- Full-screen map as the first view.
- Rainfall segmented slider or snap slider.
- Layer controls for risk, runoff, water bodies, drains, roads, and buildings.
- Legend with five risk classes.
- Click sidebar:
  - area name or grid id
  - rainfall scenario
  - final risk score
  - TWI score
  - runoff score
  - proximity to water
  - drainage inverse
  - imperviousness
  - exposure

### Phase 6: Portfolio Polish

Add:

- Methodology panel with formulas and data sources.
- Before/after scenario comparison.
- Export selected area summary as JSON or CSV.
- Hosted demo on Vercel.
- Public sample scenario files small enough to load quickly.

## Key Technical Decisions

### Ward Polygons vs Grid Cells

Start with grid cells if ward boundary access is slow. Use wards if clean boundaries are readily available.

Grid advantages:

- Uniform units.
- Easier raster aggregation.
- No ward boundary dependency.

Ward advantages:

- More intuitive civic interpretation.
- Better click sidebar story.
- Useful for prioritization narratives.

Recommendation: implement grid first, then support wards as a second aggregation mode.

### Cartosat vs Copernicus DEM

Use Copernicus DEM 30m for MVP unless Cartosat access is already solved.

Cartosat-1 10m is a stronger local-detail story, but the MVP should not depend on a fragile acquisition workflow. Keep DEM loader modular so replacing the source does not change the rest of the pipeline.

### FastAPI vs Static Files

Use FastAPI locally even if deployed static files would suffice. It gives the project a clean backend story and creates room for future scenario computation, metadata, and validation.

## Risks And Mitigations

- OSM drainage data may be incomplete: treat it as a proxy and surface confidence in docs.
- TWI in urban environments can mislead: combine it with imperviousness, water proximity, and exposure.
- SCS-CN needs land use and soil assumptions: document the assumptions and make weights configurable.
- Large GeoJSON can slow the UI: simplify geometry, use vector tiles later, and keep MVP scenario files clipped.
- Historical validation data may be sparse: add known flood points manually only as optional calibration.

## Suggested Milestones

1. Repo skeleton and docs.
2. One notebook proving DEM clipping and TWI.
3. OSM extraction script.
4. First `risk_100mm.geojson`.
5. All five scenario files.
6. FastAPI serves scenarios.
7. MapLibre UI loads and styles one scenario.
8. Slider switches scenarios smoothly.
9. Sidebar shows score breakdown.
10. Deploy and write methodology page.

