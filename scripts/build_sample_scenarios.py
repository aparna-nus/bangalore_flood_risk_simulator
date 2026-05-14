#!/usr/bin/env python3
"""Generate deterministic MVP flood-risk scenario GeoJSON files.

This is a contract-first stand-in for the future DEM/OSM/Sentinel pipeline.
It creates a Bangalore-area grid with feature properties matching the API and
frontend contract, so the product can be built before the real data work lands.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "data" / "scenarios"
RAINFALL_SCENARIOS_MM = [50, 100, 150, 200, 250]

# Approximate Bengaluru urban extent.
MIN_LON = 77.46
MAX_LON = 77.78
MIN_LAT = 12.83
MAX_LAT = 13.10
COLS = 16
ROWS = 14

LAKES = [
    (77.5863, 12.9763),  # Ulsoor
    (77.6235, 12.9495),  # Bellandur
    (77.6656, 12.9177),  # Varthur
    (77.5636, 13.0430),  # Hebbal
    (77.5929, 12.9188),  # Madiwala
    (77.5087, 12.9489),  # Nayandahalli
]

DRAINS = [
    ((77.49, 13.06), (77.74, 12.90)),
    ((77.50, 12.90), (77.69, 13.07)),
    ((77.56, 13.09), (77.62, 12.84)),
]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize_inverse_distance(distance: float, max_distance: float) -> float:
    return clamp(1.0 - distance / max_distance)


def distance(a_lon: float, a_lat: float, b_lon: float, b_lat: float) -> float:
    return math.hypot((a_lon - b_lon) * 111_000 * math.cos(math.radians(a_lat)), (a_lat - b_lat) * 111_000)


def distance_to_segment(point: tuple[float, float], segment: tuple[tuple[float, float], tuple[float, float]]) -> float:
    px, py = point
    (x1, y1), (x2, y2) = segment
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return distance(px, py, x1, y1)
    t = clamp(((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy))
    return distance(px, py, x1 + t * dx, y1 + t * dy)


def scs_runoff_mm(rainfall_mm: int, curve_number: float) -> float:
    retention = (25_400 / curve_number) - 254
    initial_abstraction = 0.2 * retention
    if rainfall_mm <= initial_abstraction:
        return 0.0
    return ((rainfall_mm - initial_abstraction) ** 2) / (rainfall_mm + 0.8 * retention)


def risk_class(score: float) -> str:
    if score < 20:
        return "very_low"
    if score < 40:
        return "low"
    if score < 60:
        return "moderate"
    if score < 80:
        return "high"
    return "severe"


def polygon_for_cell(col: int, row: int) -> list[list[list[float]]]:
    lon_step = (MAX_LON - MIN_LON) / COLS
    lat_step = (MAX_LAT - MIN_LAT) / ROWS
    west = MIN_LON + col * lon_step
    east = west + lon_step
    south = MIN_LAT + row * lat_step
    north = south + lat_step
    return [[
        [round(west, 6), round(south, 6)],
        [round(east, 6), round(south, 6)],
        [round(east, 6), round(north, 6)],
        [round(west, 6), round(north, 6)],
        [round(west, 6), round(south, 6)],
    ]]


def build_feature(col: int, row: int, rainfall_mm: int) -> dict:
    lon_step = (MAX_LON - MIN_LON) / COLS
    lat_step = (MAX_LAT - MIN_LAT) / ROWS
    lon = MIN_LON + (col + 0.5) * lon_step
    lat = MIN_LAT + (row + 0.5) * lat_step

    eastness = col / (COLS - 1)
    southness = 1.0 - row / (ROWS - 1)
    centrality = 1.0 - min(1.0, math.hypot((lon - 77.5946) / 0.18, (lat - 12.9716) / 0.14))
    valley_pattern = 0.5 + 0.5 * math.sin(col * 0.72 + row * 0.44)

    nearest_lake_m = min(distance(lon, lat, lake_lon, lake_lat) for lake_lon, lake_lat in LAKES)
    nearest_drain_m = min(distance_to_segment((lon, lat), drain) for drain in DRAINS)

    water_proximity_score = normalize_inverse_distance(nearest_lake_m, 6_500)
    drain_access = normalize_inverse_distance(nearest_drain_m, 4_200)
    drain_capacity_inverse = clamp(0.78 - 0.50 * drain_access + 0.20 * centrality + 0.12 * valley_pattern)
    impervious_score = clamp(0.28 + 0.58 * centrality + 0.18 * eastness)
    twi_score = clamp(0.18 + 0.32 * southness + 0.26 * valley_pattern + 0.20 * water_proximity_score)
    flow_accumulation_score = clamp(0.16 + 0.38 * southness + 0.26 * eastness + 0.18 * valley_pattern)
    population_exposure_score = clamp(0.20 + 0.62 * centrality + 0.20 * impervious_score)

    curve_number = 61 + 33 * impervious_score + 4 * water_proximity_score
    runoff_mm = scs_runoff_mm(rainfall_mm, curve_number)
    runoff_score = clamp(runoff_mm / max(1, rainfall_mm))
    rainfall_pressure = clamp((rainfall_mm - 40) / 220)
    runoff_accumulation_score = clamp(0.45 * runoff_score + 0.35 * flow_accumulation_score + 0.20 * rainfall_pressure)

    base_hazard = clamp(
        0.35 * twi_score
        + 0.20 * water_proximity_score
        + 0.20 * drain_capacity_inverse
        + 0.15 * impervious_score
        + 0.10 * flow_accumulation_score
    )
    scenario_hazard = clamp(0.60 * base_hazard + 0.40 * runoff_accumulation_score)
    risk_score = round(100 * clamp(0.75 * scenario_hazard + 0.25 * population_exposure_score), 1)

    area_id = f"grid_{row:02d}_{col:02d}"
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": polygon_for_cell(col, row),
        },
        "properties": {
            "area_id": area_id,
            "area_name": f"Bengaluru cell {row + 1}-{col + 1}",
            "rainfall_mm": rainfall_mm,
            "risk_score": risk_score,
            "risk_class": risk_class(risk_score),
            "base_hazard": round(base_hazard, 3),
            "scenario_hazard": round(scenario_hazard, 3),
            "runoff_score": round(runoff_score, 3),
            "runoff_accumulation_score": round(runoff_accumulation_score, 3),
            "runoff_mm": round(runoff_mm, 1),
            "curve_number": round(curve_number, 1),
            "twi_score": round(twi_score, 3),
            "water_proximity_score": round(water_proximity_score, 3),
            "drain_capacity_inverse": round(drain_capacity_inverse, 3),
            "impervious_score": round(impervious_score, 3),
            "flow_accumulation_score": round(flow_accumulation_score, 3),
            "population_exposure_score": round(population_exposure_score, 3),
            "confidence": "prototype",
        },
    }


def build_scenario(rainfall_mm: int) -> dict:
    features = [
        build_feature(col, row, rainfall_mm)
        for row in range(ROWS)
        for col in range(COLS)
    ]
    return {
        "type": "FeatureCollection",
        "name": f"bangalore_flood_risk_{rainfall_mm}mm",
        "metadata": {
            "rainfall_mm": rainfall_mm,
            "model": "synthetic_mvp_contract_v1",
            "description": "Prototype grid generated from deterministic spatial proxies. Replace with DEM/OSM/Sentinel pipeline outputs.",
        },
        "features": features,
    }


def main() -> None:
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    for rainfall_mm in RAINFALL_SCENARIOS_MM:
        scenario = build_scenario(rainfall_mm)
        output_path = SCENARIO_DIR / f"risk_{rainfall_mm:03d}mm.geojson"
        output_path.write_text(json.dumps(scenario, separators=(",", ":")), encoding="utf-8")
        print(f"Wrote {output_path.relative_to(ROOT)} ({len(scenario['features'])} features)")


if __name__ == "__main__":
    main()

