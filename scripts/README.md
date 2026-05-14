# Pipeline Scripts

Planned entrypoints:

- `build_scenarios.py`: run the full local pipeline and write scenario GeoJSON files.
- `fetch_osm.py`: download OSM infrastructure layers for the study area.
- `prepare_dem.py`: clip, reproject, and derive DEM products.

Keep scripts runnable from the repository root.

Current runnable script:

```bash
python3 scripts/build_real_scenarios.py
```

This writes real-data MVP files to `data/scenarios/` using cached or freshly downloaded OSM and elevation data.

Useful variants:

```bash
python3 scripts/build_real_scenarios.py --refresh
python3 scripts/build_real_scenarios.py --refresh --include-buildings
python3 scripts/build_sample_scenarios.py
```
