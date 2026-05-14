# Frontend

Static MapLibre GL JS app. Vercel serves the deployment copy from `public/`.

MVP interface:

- Full-screen interactive Bangalore map.
- Rainfall slider snapped to `50`, `100`, `150`, `200`, and `250` mm.
- Risk choropleth layer.
- Legend with stable risk classes.
- Click sidebar showing the score breakdown for the selected area.

Current runnable version:

```bash
python3 backend/server.py
```

Then open `http://127.0.0.1:8000`.
