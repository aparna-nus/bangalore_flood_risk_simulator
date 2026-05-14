# Bangalore Flood Risk Simulator

An interactive geospatial flood-risk simulation platform for Bangalore that combines real elevation data, hydrological approximations, OpenStreetMap infrastructure features, and rainfall-driven runoff modelling to estimate urban flood vulnerability across the city.

---

# Overview

The simulator divides Bangalore into 224 spatial grid cells and computes a flood-risk score for each cell under multiple rainfall scenarios ranging from 50mm to 250mm.

The goal is not to predict exact flood extents, but to create an interpretable urban flood-risk approximation using openly available geospatial and infrastructure datasets.

---

# What Is Being Visualised

Each map cell contains multiple environmental and urban-risk features that contribute to a final flood-risk score.

The frontend visualises:
- Flood risk severity across Bangalore
- Rainfall scenario changes
- Hydrological and urban vulnerability indicators
- Cell-level feature inspection through an interactive map UI

# Data Sources

## Elevation Data
Each grid cell receives a real elevation sample from the Open-Meteo Elevation API, backed by:

- Copernicus DEM GLO-90

Elevation is used to estimate:
- terrain slope
- local depressions
- runoff accumulation likelihood

---

## OpenStreetMap (OSM) Features

### Water Features
Fetched using the Overpass API:
- lakes
- streams
- canals
- waterways
- drainage channels

These contribute to:
- water proximity scoring
- drainage accessibility estimation

---

### Road Features
OSM road density is used as a proxy for:
- urbanization
- impervious surfaces
- exposure intensity

Higher road density generally increases runoff and reduces infiltration.

---

# Risk Components

## 1. TWI-Like Wetness Score

A simplified Topographic Wetness Index approximation based on:
- relative elevation
- nearby lower-elevation cells
- terrain flatness

This is currently a lightweight approximation and not a full raster-derived hydrological TWI implementation.

---

## 2. Water Proximity Score

Cells closer to:
- lakes
- drains
- canals
- waterways

receive higher flood susceptibility scores.

---

## 3. Drain Inverse Score

Flood risk increases when:
- mapped drains are far away
- drainage access is poor
- road density is high

This approximates reduced drainage effectiveness in dense urban areas.

---

## 4. Imperviousness Score

Estimated primarily from:
- OSM road density

Higher imperviousness leads to:
- lower infiltration
- faster runoff accumulation
- higher flood vulnerability

---

## 5. Runoff Score

Runoff estimation uses the SCS Curve Number (SCS-CN) hydrological formula.

Curve number values are estimated using:
- imperviousness
- water proximity
- terrain context

This approximates rainfall-to-runoff conversion under different rainfall intensities.

---

# Final Flood Risk Score

The final 0–100 flood-risk score combines:
- terrain hazard
- runoff accumulation
- water proximity
- drainage limitations
- urban exposure

The system recalculates scores across multiple rainfall scenarios to visualise changing flood vulnerability patterns.

---

# Rainfall Scenarios

The UI supports multiple precomputed rainfall simulations:
- 50mm
- 100mm
- 150mm
- 200mm
- 250mm

Each scenario loads a different GeoJSON layer from:

```bash
data/scenarios/
