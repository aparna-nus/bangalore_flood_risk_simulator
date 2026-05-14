let rainfallScenarios = [50, 100, 150, 200, 250];
const colors = {
  very_low: "#2f9e44",
  low: "#8bc34a",
  moderate: "#f2c94c",
  high: "#f2994a",
  severe: "#d94f45",
};

const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors",
      },
    },
    layers: [
      {
        id: "osm",
        type: "raster",
        source: "osm",
      },
    ],
  },
  center: [77.5946, 12.9716],
  zoom: 10.5,
  maxZoom: 16,
});

map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

const slider = document.querySelector("#rainfallSlider");
const rainfallValue = document.querySelector("#rainfallValue");
const areaName = document.querySelector("#areaName");
const riskScore = document.querySelector("#riskScore");
const riskClass = document.querySelector("#riskClass");
const metrics = document.querySelector("#metrics");
const metricTooltip = document.querySelector("#metricTooltip");
const riskToggle = document.querySelector("#riskToggle");
const waterToggle = document.querySelector("#waterToggle");

let activeRainfall = 100;
let activeFeatureId = null;

function riskFillExpression() {
  return [
    "match",
    ["get", "risk_class"],
    "very_low",
    colors.very_low,
    "low",
    colors.low,
    "moderate",
    colors.moderate,
    "high",
    colors.high,
    "severe",
    colors.severe,
    "#8a8f8d",
  ];
}

async function loadScenario(rainfallMm) {
  activeRainfall = rainfallMm;
  rainfallValue.textContent = rainfallMm;

  const response = await fetch(`/data/scenarios/risk_${String(rainfallMm).padStart(3, "0")}mm.geojson`);
  if (!response.ok) {
    throw new Error(`Failed to load ${rainfallMm}mm scenario`);
  }
  const geojson = await response.json();

  if (map.getSource("risk")) {
    map.getSource("risk").setData(geojson);
  } else {
    map.addSource("risk", {
      type: "geojson",
      data: geojson,
      promoteId: "area_id",
    });

    map.addLayer({
      id: "risk-fill",
      type: "fill",
      source: "risk",
      paint: {
        "fill-color": riskFillExpression(),
        "fill-opacity": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          0.82,
          0.64,
        ],
      },
    });

    map.addLayer({
      id: "risk-line",
      type: "line",
      source: "risk",
      paint: {
        "line-color": "#27332f",
        "line-opacity": 0.28,
        "line-width": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          2,
          0.7,
        ],
      },
    });

    map.on("mousemove", "risk-fill", onFeatureHover);
    map.on("mouseleave", "risk-fill", clearHover);
    map.on("click", "risk-fill", onFeatureClick);
  }

  const topFeature = [...geojson.features].sort((a, b) => b.properties.risk_score - a.properties.risk_score)[0];
  renderInspector(topFeature.properties);
}

function onFeatureHover(event) {
  map.getCanvas().style.cursor = "pointer";
  if (activeFeatureId !== null) {
    map.setFeatureState({ source: "risk", id: activeFeatureId }, { hover: false });
  }
  activeFeatureId = event.features[0].properties.area_id;
  map.setFeatureState({ source: "risk", id: activeFeatureId }, { hover: true });
}

function clearHover() {
  map.getCanvas().style.cursor = "";
  if (activeFeatureId !== null) {
    map.setFeatureState({ source: "risk", id: activeFeatureId }, { hover: false });
  }
  activeFeatureId = null;
}

function onFeatureClick(event) {
  const feature = event.features[0];
  renderInspector(feature.properties);

  new maplibregl.Popup({ closeButton: false })
    .setLngLat(event.lngLat)
    .setHTML(`<strong>${feature.properties.area_name}</strong><br>${feature.properties.risk_score}/100 at ${activeRainfall}mm`)
    .addTo(map);
}

function renderInspector(properties) {
  areaName.textContent = properties.area_name;
  riskScore.textContent = Number(properties.risk_score).toFixed(1);
  riskClass.textContent = `${String(properties.risk_class).replace("_", " ")} risk`;

  const rows = [
    metric("Runoff score", "score", properties.runoff_score, undefined, "Normalized runoff response for the selected rainfall scenario. It is derived from SCS-CN runoff depth relative to rainfall depth."),
    metric("TWI-like score", "score", properties.twi_score, undefined, "A normalized wetness proxy derived from real elevation samples: lower relative elevation, flatter local terrain, and nearby lower cells increase this score. This is not full raster TWI yet."),
    metric("Water proximity", "score", properties.water_proximity_score, undefined, "Normalized proximity score. Higher means closer to OSM water bodies, waterways, canals, streams, or drains fetched through Overpass."),
    metric("Drain inverse", "score", properties.drain_capacity_inverse, undefined, "Normalized drainage stress proxy. Higher means mapped OSM drains/canals/ditches are farther away, with road density adding urban pressure."),
    metric("Imperviousness", "score", properties.impervious_score, undefined, "Normalized urban surface proxy. Currently based mainly on OSM road density; optional building extraction can improve this later."),
    metric("Flow accumulation", "score", properties.flow_accumulation_score, undefined, "Normalized downslope accumulation proxy estimated from real elevation samples and waterway proximity. This is an MVP approximation of routed flow."),
    metric("Exposure", "score", properties.population_exposure_score, undefined, "Normalized exposure proxy based on OSM road density, with optional building density if that layer is enabled."),
    metric("Runoff depth", "raw", normaliseMetric(properties.runoff_mm, activeRainfall), `${properties.runoff_mm} mm`, "Raw runoff depth estimated with the SCS-CN equation for the selected rainfall amount."),
    metric("Elevation", "raw", normaliseMetric(properties.elevation_m, 920), `${properties.elevation_m} m`, "Raw elevation at the grid cell from Open-Meteo's Elevation API, backed by Copernicus DEM GLO-90."),
    metric("Curve number", "raw", normaliseMetric(properties.curve_number, 100), properties.curve_number, "Raw SCS-CN curve number estimated by the model from imperviousness and water proximity. Higher values produce more runoff."),
    metric("Water distance", "raw", inverseDistanceMetric(properties.water_distance_m, 7000), formatDistance(properties.water_distance_m), "Raw distance from this cell to the nearest OSM water body or mapped water feature."),
    metric("Drain distance", "raw", inverseDistanceMetric(properties.drain_distance_m, 5000), formatDistance(properties.drain_distance_m), "Raw distance from this cell to the nearest OSM drain, canal, ditch, or drainage-like waterway."),
    metric("Road features", "raw", normaliseMetric(properties.road_count_1250m, 1200), properties.road_count_1250m, "Raw count of OSM road features within roughly 1.25 km of the cell center. Used as a proxy for urbanization and exposure."),
  ];

  if (Number(properties.building_count_1250m) > 0) {
    rows.push(metric("Building features", "raw", normaliseMetric(properties.building_count_1250m, 1200), properties.building_count_1250m, "Raw count of OSM building features within roughly 1.25 km. This appears only when the optional building layer is generated."));
  }

  metrics.innerHTML = rows.map((row) => {
    const value = Number(row.value);
    const percent = Math.round(Math.max(0, Math.min(1, value)) * 100);
    const shown = row.displayValue ?? value.toFixed(2);
    return `
      <div class="metric" tabindex="0" aria-describedby="metricTooltip" data-tooltip="${row.tooltip}">
        <dt>
          <span>${row.label}</span>
          <span class="metric-kind ${row.kind}">${row.kind}</span>
        </dt>
        <dd>${shown}</dd>
        <div class="bar"><span style="--value: ${percent}%"></span></div>
      </div>
    `;
  }).join("");
}

function metric(label, kind, value, displayValue, tooltip) {
  return {
    label,
    kind,
    value,
    displayValue,
    tooltip,
  };
}

function normaliseMetric(value, maxValue) {
  return Math.max(0, Math.min(1, Number(value) / maxValue));
}

function inverseDistanceMetric(value, maxValue) {
  return Math.max(0, Math.min(1, 1 - Number(value) / maxValue));
}

function formatDistance(value) {
  const meters = Number(value);
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

function setLayerVisibility(layerId, visible) {
  if (!map.getLayer(layerId)) return;
  map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
}

slider.addEventListener("input", () => {
  const rainfallMm = rainfallScenarios[Number(slider.value)];
  loadScenario(rainfallMm).catch((error) => {
    console.error(error);
  });
});

riskToggle.addEventListener("click", () => {
  riskToggle.classList.toggle("is-active");
  const visible = riskToggle.classList.contains("is-active");
  setLayerVisibility("risk-fill", visible);
  setLayerVisibility("risk-line", visible);
});

waterToggle.addEventListener("click", () => {
  waterToggle.classList.toggle("is-active");
  const active = waterToggle.classList.contains("is-active");
  if (map.getLayer("water-emphasis")) {
    setLayerVisibility("water-emphasis", active);
  }
});

metrics.addEventListener("mouseover", (event) => {
  const metricRow = event.target.closest(".metric");
  if (!metricRow) return;
  showMetricTooltip(metricRow, event.clientX, event.clientY);
});

metrics.addEventListener("mousemove", (event) => {
  const metricRow = event.target.closest(".metric");
  if (!metricRow || metricTooltip.classList.contains("is-hidden")) return;
  positionMetricTooltip(event.clientX, event.clientY);
});

metrics.addEventListener("mouseout", (event) => {
  if (!event.relatedTarget || !event.currentTarget.contains(event.relatedTarget)) {
    hideMetricTooltip();
  }
});

metrics.addEventListener("focusin", (event) => {
  const metricRow = event.target.closest(".metric");
  if (!metricRow) return;
  const rect = metricRow.getBoundingClientRect();
  showMetricTooltip(metricRow, rect.left + 20, rect.bottom);
});

metrics.addEventListener("focusout", hideMetricTooltip);

function showMetricTooltip(metricRow, x, y) {
  metricTooltip.textContent = metricRow.dataset.tooltip;
  metricTooltip.classList.add("is-visible");
  positionMetricTooltip(x, y);
}

function hideMetricTooltip() {
  metricTooltip.classList.remove("is-visible");
}

function positionMetricTooltip(x, y) {
  const margin = 14;
  const width = 300;
  const left = Math.min(window.innerWidth - width - margin, x + margin);
  const top = Math.min(window.innerHeight - 120, y + margin);
  metricTooltip.style.left = `${Math.max(margin, left)}px`;
  metricTooltip.style.top = `${Math.max(margin, top)}px`;
}

async function loadScenarioManifest() {
  try {
    const response = await fetch("/data/scenarios.json");
    if (!response.ok) return;
    const manifest = await response.json();
    rainfallScenarios = manifest.rainfall_mm ?? rainfallScenarios;
    activeRainfall = manifest.default ?? activeRainfall;
    slider.max = String(rainfallScenarios.length - 1);
    slider.value = String(Math.max(0, rainfallScenarios.indexOf(activeRainfall)));
  } catch (error) {
    console.warn("Using built-in scenario list", error);
  }
}

map.on("load", async () => {
  map.addSource("water-points", {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: [
        [77.5863, 12.9763, "Ulsoor Lake"],
        [77.6235, 12.9495, "Bellandur Lake"],
        [77.6656, 12.9177, "Varthur Lake"],
        [77.5636, 13.0430, "Hebbal Lake"],
        [77.5929, 12.9188, "Madiwala Lake"],
        [77.5087, 12.9489, "Nayandahalli Lake"],
      ].map(([lon, lat, name]) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [lon, lat] },
        properties: { name },
      })),
    },
  });

  map.addLayer({
    id: "water-emphasis",
    type: "circle",
    source: "water-points",
    layout: {
      visibility: "none",
    },
    paint: {
      "circle-radius": 8,
      "circle-color": "#1f78b4",
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });

  await loadScenarioManifest();
  loadScenario(activeRainfall).catch((error) => {
    console.error(error);
  });
});
