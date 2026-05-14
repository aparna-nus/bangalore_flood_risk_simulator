#!/usr/bin/env python3
"""Build real-data v1 flood-risk scenario GeoJSON files.

This keeps the same frontend/API contract as the prototype generator, but
derives features from live/cached public data:

- OpenStreetMap via Overpass: roads, buildings, waterways, drains, water bodies
- Open-Meteo Elevation API: Copernicus DEM GLO-90 elevation samples

It is intentionally dependency-light so the repo remains runnable before the
heavier raster stack is introduced.
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SCENARIO_DIR = ROOT / "data" / "scenarios"

RAINFALL_SCENARIOS_MM = [50, 100, 150, 200, 250]

MIN_LON = 77.46
MAX_LON = 77.78
MIN_LAT = 12.83
MAX_LAT = 13.10
COLS = 16
ROWS = 14

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"


OSM_QUERIES = {
    "water": """
        [out:json][timeout:120];
        (
          way["natural"="water"]({bbox});
          relation["natural"="water"]({bbox});
          way["water"~"lake|reservoir|pond"]({bbox});
          relation["water"~"lake|reservoir|pond"]({bbox});
        );
        out center tags qt;
    """,
    "waterways": """
        [out:json][timeout:120];
        (
          way["waterway"~"river|stream|canal|drain|ditch"]({bbox});
          relation["waterway"~"river|stream|canal|drain|ditch"]({bbox});
        );
        out center tags qt;
    """,
    "roads": """
        [out:json][timeout:120];
        (
          way["highway"]({bbox});
        );
        out center tags qt;
    """,
}

BUILDINGS_QUERY = """
        [out:json][timeout:90];
        (
          way["building"]({bbox});
          relation["building"]({bbox});
        );
        out center tags qt 20000;
    """


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def distance_m(a_lon: float, a_lat: float, b_lon: float, b_lat: float) -> float:
    return math.hypot((a_lon - b_lon) * 111_000 * math.cos(math.radians(a_lat)), (a_lat - b_lat) * 111_000)


def cell_centers() -> list[dict]:
    lon_step = (MAX_LON - MIN_LON) / COLS
    lat_step = (MAX_LAT - MIN_LAT) / ROWS
    centers = []
    for row in range(ROWS):
        for col in range(COLS):
            west = MIN_LON + col * lon_step
            east = west + lon_step
            south = MIN_LAT + row * lat_step
            north = south + lat_step
            centers.append({
                "row": row,
                "col": col,
                "lon": (west + east) / 2,
                "lat": (south + north) / 2,
                "bounds": (west, south, east, north),
            })
    return centers


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


def request_json(url: str, data: bytes | None = None, timeout: int = 180) -> dict:
    headers = {"User-Agent": "bangalore-flood-risk-simulator/0.1 (portfolio MVP)"}
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_overpass_layer(name: str, *, refresh: bool) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"osm_{name}.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    bbox = f"{MIN_LAT},{MIN_LON},{MAX_LAT},{MAX_LON}"
    template = BUILDINGS_QUERY if name == "buildings" else OSM_QUERIES[name]
    query = " ".join(template.format(bbox=bbox).split())
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    payload = request_json(OVERPASS_URL, data=data)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    time.sleep(1.0)
    return payload


def element_points(payload: dict) -> list[dict]:
    points = []
    for element in payload.get("elements", []):
        center = element.get("center")
        lon = element.get("lon") if "lon" in element else center.get("lon") if center else None
        lat = element.get("lat") if "lat" in element else center.get("lat") if center else None
        if lon is None or lat is None:
            continue
        points.append({
            "lon": float(lon),
            "lat": float(lat),
            "tags": element.get("tags", {}),
            "type": element.get("type"),
            "id": element.get("id"),
        })
    return points


def fetch_elevations(centers: list[dict], *, refresh: bool) -> list[float]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / "elevation_grid_open_meteo.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))["elevation"]

    elevations: list[float] = []
    for start in range(0, len(centers), 100):
        chunk = centers[start:start + 100]
        params = urllib.parse.urlencode({
            "latitude": ",".join(f"{point['lat']:.6f}" for point in chunk),
            "longitude": ",".join(f"{point['lon']:.6f}" for point in chunk),
        })
        payload = request_json(f"{ELEVATION_URL}?{params}", timeout=60)
        elevations.extend(float(value) for value in payload["elevation"])
        time.sleep(0.4)

    cache_path.write_text(json.dumps({"elevation": elevations}), encoding="utf-8")
    return elevations


def nearest_distance(point: dict, features: Iterable[dict], fallback: float) -> float:
    nearest = fallback
    for feature in features:
        nearest = min(nearest, distance_m(point["lon"], point["lat"], feature["lon"], feature["lat"]))
    return nearest


def count_within(point: dict, features: Iterable[dict], radius_m: float) -> int:
    count = 0
    for feature in features:
        if distance_m(point["lon"], point["lat"], feature["lon"], feature["lat"]) <= radius_m:
            count += 1
    return count


def minmax_scale(values: list[float], value: float) -> float:
    low = min(values)
    high = max(values)
    if high == low:
        return 0.5
    return clamp((value - low) / (high - low))


def neighbor_elevation(elevations: list[float], row: int, col: int) -> list[float]:
    values = []
    for d_row in (-1, 0, 1):
        for d_col in (-1, 0, 1):
            if d_row == 0 and d_col == 0:
                continue
            n_row = row + d_row
            n_col = col + d_col
            if 0 <= n_row < ROWS and 0 <= n_col < COLS:
                values.append(elevations[n_row * COLS + n_col])
    return values


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


def build_base_cells(refresh: bool, include_buildings: bool) -> list[dict]:
    centers = cell_centers()
    layers = {
        name: element_points(fetch_overpass_layer(name, refresh=refresh))
        for name in OSM_QUERIES
    }
    if include_buildings:
        layers["buildings"] = element_points(fetch_overpass_layer("buildings", refresh=refresh))
    else:
        layers["buildings"] = []
    for name, features in layers.items():
        print(f"Loaded {len(features):,} OSM {name} features")
    elevations = fetch_elevations(centers, refresh=refresh)
    print(f"Loaded {len(elevations):,} elevation samples")

    raw_rows = []
    for idx, point in enumerate(centers):
        row = point["row"]
        col = point["col"]
        nearby_elevations = neighbor_elevation(elevations, row, col)
        elevation = elevations[idx]
        lower_neighbor_count = sum(1 for value in nearby_elevations if value < elevation)
        local_relief = max(nearby_elevations) - min(nearby_elevations) if nearby_elevations else 0

        water_distance = nearest_distance(point, layers["water"], 10_000)
        waterway_distance = nearest_distance(point, layers["waterways"], 8_000)
        drain_points = [
            feature for feature in layers["waterways"]
            if feature["tags"].get("waterway") in {"drain", "canal", "ditch"}
        ]
        drain_distance = nearest_distance(point, drain_points, 8_000)
        building_count = count_within(point, layers["buildings"], 1_250)
        road_count = count_within(point, layers["roads"], 1_250)

        raw_rows.append({
            **point,
            "elevation_m": elevation,
            "local_relief_m": local_relief,
            "lower_neighbor_count": lower_neighbor_count,
            "water_distance_m": water_distance,
            "waterway_distance_m": waterway_distance,
            "drain_distance_m": drain_distance,
            "building_count_1250m": building_count,
            "road_count_1250m": road_count,
        })

    building_values = [row["building_count_1250m"] for row in raw_rows]
    road_values = [row["road_count_1250m"] for row in raw_rows]
    relief_values = [row["local_relief_m"] for row in raw_rows]
    elevation_values = [row["elevation_m"] for row in raw_rows]

    for row in raw_rows:
        low_elevation_score = 1.0 - minmax_scale(elevation_values, row["elevation_m"])
        flatness_score = 1.0 - minmax_scale(relief_values, row["local_relief_m"])
        depression_score = 1.0 - row["lower_neighbor_count"] / 8
        twi_score = clamp(0.45 * low_elevation_score + 0.35 * flatness_score + 0.20 * depression_score)

        water_proximity_score = clamp(
            0.65 * (1 - min(row["water_distance_m"], 7_000) / 7_000)
            + 0.35 * (1 - min(row["waterway_distance_m"], 5_000) / 5_000)
        )
        drain_access_score = 1 - min(row["drain_distance_m"], 5_000) / 5_000
        drain_capacity_inverse = clamp(0.82 - 0.55 * drain_access_score + 0.18 * minmax_scale(road_values, row["road_count_1250m"]))
        building_signal = minmax_scale(building_values, row["building_count_1250m"]) if include_buildings else minmax_scale(road_values, row["road_count_1250m"])
        road_signal = minmax_scale(road_values, row["road_count_1250m"])
        impervious_score = clamp(0.62 * building_signal + 0.38 * road_signal)
        flow_accumulation_score = clamp(0.45 * low_elevation_score + 0.35 * depression_score + 0.20 * waterway_proximity_score(row))
        population_exposure_score = clamp(0.65 * building_signal + 0.35 * road_signal)

        row.update({
            "twi_score": twi_score,
            "water_proximity_score": water_proximity_score,
            "drain_capacity_inverse": drain_capacity_inverse,
            "impervious_score": impervious_score,
            "flow_accumulation_score": flow_accumulation_score,
            "population_exposure_score": population_exposure_score,
        })

    return raw_rows


def waterway_proximity_score(row: dict) -> float:
    return 1 - min(row["waterway_distance_m"], 5_000) / 5_000


def build_feature(row: dict, rainfall_mm: int) -> dict:
    curve_number = clamp(61 + 31 * row["impervious_score"] + 5 * row["water_proximity_score"], 35, 98)
    runoff_mm = scs_runoff_mm(rainfall_mm, curve_number)
    runoff_score = clamp(runoff_mm / max(1, rainfall_mm))
    rainfall_pressure = clamp((rainfall_mm - 40) / 220)
    runoff_accumulation_score = clamp(
        0.45 * runoff_score
        + 0.35 * row["flow_accumulation_score"]
        + 0.20 * rainfall_pressure
    )

    base_hazard = clamp(
        0.35 * row["twi_score"]
        + 0.20 * row["water_proximity_score"]
        + 0.20 * row["drain_capacity_inverse"]
        + 0.15 * row["impervious_score"]
        + 0.10 * row["flow_accumulation_score"]
    )
    scenario_hazard = clamp(0.60 * base_hazard + 0.40 * runoff_accumulation_score)
    risk_score = round(100 * clamp(0.75 * scenario_hazard + 0.25 * row["population_exposure_score"]), 1)

    area_id = f"grid_{row['row']:02d}_{row['col']:02d}"
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": polygon_for_cell(row["col"], row["row"]),
        },
        "properties": {
            "area_id": area_id,
            "area_name": f"Bengaluru cell {row['row'] + 1}-{row['col'] + 1}",
            "rainfall_mm": rainfall_mm,
            "risk_score": risk_score,
            "risk_class": risk_class(risk_score),
            "base_hazard": round(base_hazard, 3),
            "scenario_hazard": round(scenario_hazard, 3),
            "runoff_score": round(runoff_score, 3),
            "runoff_accumulation_score": round(runoff_accumulation_score, 3),
            "runoff_mm": round(runoff_mm, 1),
            "curve_number": round(curve_number, 1),
            "twi_score": round(row["twi_score"], 3),
            "water_proximity_score": round(row["water_proximity_score"], 3),
            "drain_capacity_inverse": round(row["drain_capacity_inverse"], 3),
            "impervious_score": round(row["impervious_score"], 3),
            "flow_accumulation_score": round(row["flow_accumulation_score"], 3),
            "population_exposure_score": round(row["population_exposure_score"], 3),
            "elevation_m": round(row["elevation_m"], 1),
            "water_distance_m": round(row["water_distance_m"]),
            "waterway_distance_m": round(row["waterway_distance_m"]),
            "drain_distance_m": round(row["drain_distance_m"]),
            "building_count_1250m": row["building_count_1250m"],
            "road_count_1250m": row["road_count_1250m"],
            "confidence": "real_data_v1",
        },
    }


def build_scenario(base_rows: list[dict], rainfall_mm: int) -> dict:
    return {
        "type": "FeatureCollection",
        "name": f"bangalore_flood_risk_{rainfall_mm}mm",
        "metadata": {
            "rainfall_mm": rainfall_mm,
            "model": "real_data_v1_osm_open_meteo",
            "sources": [
                "OpenStreetMap via Overpass API",
                "Open-Meteo Elevation API / Copernicus DEM GLO-90",
            ],
            "description": "Real-data MVP using OSM infrastructure and Copernicus DEM elevation samples. Hydrology remains an approximate grid model.",
        },
        "features": [build_feature(row, rainfall_mm) for row in base_rows],
    }


def main() -> None:
    args = set(sys.argv)
    refresh = "--refresh" in args
    include_buildings = "--include-buildings" in args
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    base_rows = build_base_cells(refresh=refresh, include_buildings=include_buildings)

    summary_path = ROOT / "data" / "processed" / "real_data_v1_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({
        "grid_cells": len(base_rows),
        "rainfall_scenarios_mm": RAINFALL_SCENARIOS_MM,
        "source_model": "real_data_v1_osm_open_meteo",
        "include_buildings": include_buildings,
        "bounds": {
            "min_lon": MIN_LON,
            "min_lat": MIN_LAT,
            "max_lon": MAX_LON,
            "max_lat": MAX_LAT,
        },
    }, indent=2), encoding="utf-8")

    for rainfall_mm in RAINFALL_SCENARIOS_MM:
        scenario = build_scenario(base_rows, rainfall_mm)
        output_path = SCENARIO_DIR / f"risk_{rainfall_mm:03d}mm.geojson"
        output_path.write_text(json.dumps(scenario, separators=(",", ":")), encoding="utf-8")
        print(f"Wrote {output_path.relative_to(ROOT)} ({len(scenario['features'])} features)")


if __name__ == "__main__":
    main()
