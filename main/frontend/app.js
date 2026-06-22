// ============================================================
// Configuration
// ============================================================
const API_BASE = window.location.origin; // change if your backend runs elsewhere

const TARGET_META = {
  Total_PowerConsumption: { label: "Total", color: "#6C3FE0" },
  F1_132KV_PowerConsumption: { label: "F1", color: "#1FAE6B" },
  F2_132KV_PowerConsumption: { label: "F2", color: "#E58A2A" },
  F3_132KV_PowerConsumption: { label: "F3", color: "#E5484D" },
};

// Validation MAPE from the model training/evaluation notebook
const MODEL_MAPE = {
  Total_PowerConsumption: 0.61,
  F1_132KV_PowerConsumption: 0.77,
  F2_132KV_PowerConsumption: 0.77,
  F3_132KV_PowerConsumption: 2.25,
};

let forecastChart = null;
let visibleTargets = new Set(Object.keys(TARGET_META)); // all visible by default

// ============================================================
// Fetch helpers
// ============================================================
async function fetchForecast() {
  const res = await fetch(`${API_BASE}/forecast`);
  if (!res.ok) throw new Error(`/forecast failed: ${res.status}`);
  return res.json();
}

async function fetchContext() {
  const res = await fetch(`${API_BASE}/context`);
  if (!res.ok) throw new Error(`/context failed: ${res.status}`);
  return res.json();
}

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}
function fmtShortTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}
function fmtKw(v) {
  return Math.round(v).toLocaleString("en-IN");
}

// ============================================================
// Render: Top stats row
// ============================================================
function renderStatsRow(forecastData) {
  const rows = forecastData.forecast;
  const totals = rows.map(r => r.Total_PowerConsumption);
  const peak = Math.max(...totals);
  const peakRow = rows[totals.indexOf(peak)];
  const low = Math.min(...totals);
  const lowRow = rows[totals.indexOf(low)];
  const avg = totals.reduce((a, b) => a + b, 0) / totals.length;

  const statsRow = document.getElementById("stats-row");
  statsRow.innerHTML = `
    <div class="stat-card">
      <div class="sc-label">Peak Forecast Load <span class="badge mid">${fmtShortTime(peakRow.datetime)}</span></div>
      <div class="sc-value">${fmtKw(peak)} kW</div>
    </div>
    <div class="stat-card">
      <div class="sc-label">Lowest Forecast Load <span class="badge good">${fmtShortTime(lowRow.datetime)}</span></div>
      <div class="sc-value">${fmtKw(low)} kW</div>
    </div>
    <div class="stat-card">
      <div class="sc-label">Average Forecast Load</div>
      <div class="sc-value">${fmtKw(avg)} kW</div>
    </div>
    <div class="stat-card">
      <div class="sc-label">Forecast Horizon</div>
      <div class="sc-value">${forecastData.horizon_steps} steps</div>
    </div>
  `;
}

// ============================================================
// Render: Main forecast chart
// ============================================================
function renderForecastChart(forecastData, holidayDatetimes) {
  const labels = forecastData.forecast.map(r => fmtShortTime(r.datetime));
  const holidaySet = new Set(holidayDatetimes);

  const datasets = Object.keys(TARGET_META).map(key => {
    const meta = TARGET_META[key];
    return {
      label: meta.label,
      data: forecastData.forecast.map(r => r[key]),
      borderColor: meta.color,
      backgroundColor: meta.color + "22",
      borderWidth: key === "Total_PowerConsumption" ? 3 : 2,
      borderDash: key === "F3_132KV_PowerConsumption" ? [6, 4] : [],
      pointRadius: 0,
      tension: 0.35,
      hidden: !visibleTargets.has(key),
      fill: key === "Total_PowerConsumption",
    };
  });

  const ctx = document.getElementById("forecastChart").getContext("2d");
  if (forecastChart) forecastChart.destroy();

  forecastChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1E1B2E",
          padding: 10,
          titleFont: { weight: "600" },
          callbacks: {
            label: (item) => `${item.dataset.label}: ${fmtKw(item.parsed.y)} kW`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: 8, color: "#9B98AC", font: { size: 11 } },
        },
        y: {
          grid: { color: "#ECEAF4" },
          ticks: { color: "#9B98AC", font: { size: 11 }, callback: (v) => fmtKw(v) },
        },
      },
    },
  });

  renderLegendToggles();
}

function renderLegendToggles() {
  const container = document.getElementById("legend-toggles");
  container.innerHTML = "";
  Object.entries(TARGET_META).forEach(([key, meta]) => {
    const el = document.createElement("div");
    el.className = "legend-toggle" + (visibleTargets.has(key) ? "" : " off");
    el.innerHTML = `<span class="swatch" style="background:${meta.color}"></span>${meta.label}`;
    el.onclick = () => {
      if (visibleTargets.has(key)) visibleTargets.delete(key);
      else visibleTargets.add(key);
      el.classList.toggle("off");
      const idx = Object.keys(TARGET_META).indexOf(key);
      forecastChart.setDatasetVisibility(idx, visibleTargets.has(key));
      forecastChart.update();
    };
    container.appendChild(el);
  });
}

// ============================================================
// Render: Feeder comparison (bar chart: peak/avg/low per feeder)
// + Share of total donut (at forecast peak time)
// ============================================================
let feederBarChart = null;
let shareDonutChart = null;

function renderFeederComparisonChart(forecastData) {
  const rows = forecastData.forecast;
  const feederKeys = Object.keys(TARGET_META).filter(k => k !== "Total_PowerConsumption");

  const stats = feederKeys.map(key => {
    const vals = rows.map(r => r[key]);
    return {
      key,
      label: TARGET_META[key].label,
      color: TARGET_META[key].color,
      peak: Math.max(...vals),
      avg: vals.reduce((a, b) => a + b, 0) / vals.length,
      low: Math.min(...vals),
    };
  });

  const ctx = document.getElementById("feederBarChart").getContext("2d");
  if (feederBarChart) feederBarChart.destroy();
  feederBarChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: stats.map(s => s.label),
      datasets: [
        { label: "Peak", data: stats.map(s => s.peak), backgroundColor: stats.map(s => s.color), borderRadius: 6 },
        { label: "Average", data: stats.map(s => s.avg), backgroundColor: stats.map(s => s.color + "99"), borderRadius: 6 },
        { label: "Lowest", data: stats.map(s => s.low), backgroundColor: stats.map(s => s.color + "44"), borderRadius: 6 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: (item) => `${item.dataset.label}: ${fmtKw(item.parsed.y)} kW` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 12, weight: "600" } } },
        y: { grid: { color: "#ECEAF4" }, ticks: { callback: (v) => fmtKw(v), font: { size: 11 } } },
      },
    },
  });

  // Share-of-total donut, using the forecast's peak-load timestamp as the snapshot moment
  const totalVals = rows.map(r => r.Total_PowerConsumption);
  const peakIdx = totalVals.indexOf(Math.max(...totalVals));
  const peakRow = rows[peakIdx];

  const donutCtx = document.getElementById("shareDonutChart").getContext("2d");
  if (shareDonutChart) shareDonutChart.destroy();
  shareDonutChart = new Chart(donutCtx, {
    type: "doughnut",
    data: {
      labels: feederKeys.map(k => TARGET_META[k].label),
      datasets: [{
        data: feederKeys.map(k => peakRow[k]),
        backgroundColor: feederKeys.map(k => TARGET_META[k].color),
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: (item) => `${item.label}: ${fmtKw(item.parsed)} kW` } },
      },
    },
  });

  document.getElementById("share-donut-caption").textContent =
    `Feeder share of Total at forecasted peak (${fmtShortTime(peakRow.datetime)})`;
}


function miniLineChart(canvasId, values, color) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: values.map((_, i) => i),
      datasets: [{ data: values, borderColor: color, borderWidth: 2, pointRadius: 0, tension: 0.4, fill: false }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      elements: { line: { borderJoinStyle: "round" } },
    },
  });
}

function renderWeather(contextData) {
  const weather = contextData.weather;
  const first = weather[0];

  document.getElementById("temp-value").innerHTML =
    `${first.temperature_c}<span class="wt-unit">°C</span>`;

  document.getElementById("humidity-value").innerHTML =
    `${first.humidity_pct}<span class="wt-unit">%</span>`;

  document.getElementById("cloud-value").innerHTML =
    `${first.cloud_cover_pct}<span class="wt-unit">%</span>`;

  // ✅ Convert m/s → km/h
  // ✅ Always read directly, no strict undefined check
  const windVal = first.wind_speed_mps;

  // Convert to km/h safely
  const windKmph = (windVal !== null && windVal !== undefined)
    ? (windVal * 3.6)
    : null;

  document.getElementById("wind-value").innerHTML =
    windKmph !== null
      ? `${windKmph.toFixed(1)}<span class="wt-unit"> km/h</span>`
      : `<span class="wt-unit" style="font-size:13px;">not exposed by /context</span>`;

  // Mini charts
  miniLineChart("tempMiniChart", weather.map(w => w.temperature_c), "#6C3FE0");
  miniLineChart("humidityMiniChart", weather.map(w => w.humidity_pct), "#1FAE6B");
  miniLineChart("cloudMiniChart", weather.map(w => w.cloud_cover_pct), "#E58A2A");

  // ✅ Fan strip (still uses m/s threshold = 2.5, consistent with model)
  const fanStrip = document.getElementById("fan-strip");
  fanStrip.innerHTML = "";

  weather.forEach(w => {
    const isOn = (w.wind_speed_mps !== null && w.wind_speed_mps !== undefined) && (w.wind_speed_mps > 2.5);
    const seg = document.createElement("div");
    if (isOn) seg.classList.add("on");
    fanStrip.appendChild(seg);
  });
}
// ============================================================
// Render: Model accuracy
// ============================================================
function renderModelAccuracy() {
  const container = document.getElementById("model-accuracy-rows");
  const maxMape = Math.max(...Object.values(MODEL_MAPE));
  container.innerHTML = Object.entries(TARGET_META).map(([key, meta]) => {
    const mape = MODEL_MAPE[key];
    const widthPct = (mape / maxMape) * 100;
    return `
      <div class="model-row">
        <div class="model-name"><span class="swatch" style="background:${meta.color}"></span>${meta.label}</div>
        <div class="model-bar-wrap"><div class="model-bar" style="width:${widthPct}%; background:${meta.color}"></div></div>
        <div class="model-mape">${mape}%</div>
      </div>
    `;
  }).join("");
}

// ============================================================
// Render: Holidays
// ============================================================
function renderHolidays(contextData) {
  const list = document.getElementById("holiday-list");
  const holidays = contextData.holidays || [];

  if (holidays.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="es-icon">📅</div>
        <div class="es-text">No holidays fall within this 24-hour forecast window.</div>
      </div>`;
    return;
  }

  list.innerHTML = holidays.map(h => `
    <div class="holiday-item">
      <div class="hi-icon">🎉</div>
      <div>
        <div class="hi-name">${h.holiday_name}</div>
        <div class="hi-date">${fmtTime(h.datetime)}</div>
      </div>
    </div>
  `).join("");
}

// ============================================================
// Main load function
// ============================================================
async function loadDashboard() {
  const refreshBtn = document.getElementById("refresh-btn");
  const statusPill = document.getElementById("status-pill");
  refreshBtn.disabled = true;
  refreshBtn.textContent = "Loading…";
  statusPill.textContent = "Syncing…";

  try {
    const [forecastData, contextData] = await Promise.all([fetchForecast(), fetchContext()]);

    document.getElementById("forecast-window-label").textContent =
      `${fmtTime(forecastData.start_time)} → ${fmtTime(forecastData.forecast[forecastData.forecast.length - 1].datetime)} · Dhanbad, Jharkhand`;

    const holidayDatetimes = (contextData.holidays || []).map(h => h.datetime);

    const steps = [
      ["stats", () => renderStatsRow(forecastData)],
      ["forecast chart", () => renderForecastChart(forecastData, holidayDatetimes)],
      ["feeder comparison chart", () => renderFeederComparisonChart(forecastData)],
      ["weather", () => renderWeather(contextData)],
      ["model accuracy", () => renderModelAccuracy()],
      ["holidays", () => renderHolidays(contextData)],
    ];

    let allOk = true;
    for (const [name, fn] of steps) {
      try {
        fn();
      } catch (stepErr) {
        allOk = false;
        console.error(`Render step failed: ${name}`, stepErr);
      }
    }

    statusPill.textContent = allOk ? "Live" : "Partial";
  } catch (err) {
    console.error(err);
    statusPill.textContent = "Error";
    document.getElementById("forecast-window-label").textContent =
      "Could not reach the forecasting API — check that the backend is running on " + API_BASE;
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "↻ Refresh Forecast";
  }
}

document.getElementById("refresh-btn").addEventListener("click", loadDashboard);

document.querySelectorAll(".nav-item[data-target]").forEach(item => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    item.classList.add("active");
    document.getElementById(item.dataset.target)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

loadDashboard();
