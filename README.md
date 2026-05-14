Overview of what's being visualised in the map/UI:

**Data Prep**
- Map grid: Bangalore is split into 224 grid cells in scripts/build_real_scenarios.py.

**Individual things we calculate to get the final risk score**
- Elevation: Each cell gets a real elevation sample from Open-Meteo’s Elevation API, backed by Copernicus DEM GLO-90.
- OSM water data: Water bodies and waterways/drains are fetched from OpenStreetMap through Overpass API.
- OSM roads: Road features are fetched from OpenStreetMap and used as a proxy for urbanization/imperviousness and exposure.
- TWI-like score: Estimated from relative elevation, local flatness, and whether nearby cells are lower. It is an approximation, not full raster TWI yet.
- Water proximity score: Higher if a cell is closer to lakes, water bodies, streams, canals, or drains.
- Drain inverse score: Higher risk when mapped drains/canals/ditches are farther away or road density is high.
- Imperviousness score: Currently estimated mostly from OSM road density. Building density is optional but off by default.
- Runoff score: Uses the SCS-CN formula. Curve number is estimated from imperviousness and water proximity.
- Final risk score: Combines base hazard, rainfall-driven runoff accumulation, and exposure into a 0-100 score.

** UI/UX Features**
- UI slider: Changing rainfall from 50 to 250mm loads a different precomputed GeoJSON file from data/scenarios.
- Click inspector: Reads the selected cell’s GeoJSON properties directly: risk, runoff, elevation, TWI, water proximity, drain distance, road features, etc.

**Deploying to Vercel**
- Vercel serves the static app from `public/`.
- The browser fetches precomputed files from `public/data/scenarios/`.
- No Python backend is needed in production.
- Run `make data` before deploying if you refresh the real-data scenario files.
- Deploy by importing the repo in Vercel, or from the CLI with `vercel`.
- The local Python server is only for previewing the same static app at `http://127.0.0.1:8000`.
