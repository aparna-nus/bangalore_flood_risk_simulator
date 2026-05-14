#!/usr/bin/env python3
"""Sync generated scenario files into Vercel's static public directory."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "data" / "scenarios"
PUBLIC_SCENARIO_DIR = ROOT / "public" / "data" / "scenarios"
PUBLIC_MANIFEST = ROOT / "public" / "data" / "scenarios.json"
RAINFALL_SCENARIOS_MM = [50, 100, 150, 200, 250]


def main() -> None:
    PUBLIC_SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    for rainfall_mm in RAINFALL_SCENARIOS_MM:
        source = SCENARIO_DIR / f"risk_{rainfall_mm:03d}mm.geojson"
        target = PUBLIC_SCENARIO_DIR / source.name
        if not source.exists():
            raise FileNotFoundError(f"Missing scenario file: {source}")
        shutil.copyfile(source, target)
        print(f"Synced {target.relative_to(ROOT)}")

    PUBLIC_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_MANIFEST.write_text(json.dumps({
        "rainfall_mm": RAINFALL_SCENARIOS_MM,
        "default": 100,
        "unit": "mm",
        "model": "real_data_v1_osm_open_meteo",
        "sources": [
            "OpenStreetMap via Overpass API",
            "Open-Meteo Elevation API / Copernicus DEM GLO-90",
        ],
    }, indent=2), encoding="utf-8")
    print(f"Synced {PUBLIC_MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

