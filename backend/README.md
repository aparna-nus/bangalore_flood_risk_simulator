# Backend

Optional local preview server. Vercel deployment does not use this backend.

MVP endpoints:

- `GET /health`
- `GET /scenarios`
- `GET /risk/{rainfall_mm}`

For local development, this serves `public/` plus compatibility endpoints for `data/scenarios/*.geojson`. Add PostGIS or object storage only after the static product loop needs it.

Current runnable version:

```bash
python3 backend/server.py
```

The server uses Python's standard library for now so the MVP can run before dependency setup. It serves both the API and the static app.
