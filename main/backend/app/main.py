"""
FastAPI backend for the Intelligent Power Demand Forecasting system (APU / Dhanbad).

Endpoints:
  GET /forecast  -> 24-hour (144-step) demand forecast for Total, F1, F2, F3
  GET /context   -> weather (temperature, humidity, cloud cover) + localized
                     holiday data for the same forecast period, for frontend visualization
  GET /health    -> simple health check
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from app.forecasting import generate_forecast, TARGETS, N_STEPS
from app.weather import get_weather_for_horizon
from app.holidays_calendar import get_holiday_flags
# for frontend
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
app = FastAPI(
    title="Apex Power & Utilities (APU) — Demand Forecasting API",
    description="Forecasts 24-hour electricity demand for Total, F1, F2, F3 feeders, "
                "with live Dhanbad weather and localized holiday context.",
    version="1.0.0",
)
# serve frontend
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")

# Allow the frontend (served from a different origin/port) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your actual frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_forecast_start_time() -> pd.Timestamp:
    """The forecast always starts at 'now', rounded down to the nearest 10-minute block."""
    now = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)
    floored_minute = (now.minute // 10) * 10
    return now.replace(minute=floored_minute, second=0, microsecond=0) + pd.Timedelta(minutes=10)


@app.get("/health")
def health_check():
    return {"status": "ok", "targets": TARGETS, "horizon_steps": N_STEPS}


@app.get("/forecast")
def get_forecast():
    """
    Returns a 24-hour (144-step, 10-min resolution) demand forecast
    for Total, F1, F2, and F3, starting from the current time.
    """
    try:
        start_time = _get_forecast_start_time()
        weather_df = get_weather_for_horizon(start_time, n_steps=N_STEPS)
        forecast_df = generate_forecast(start_time, weather_df, n_steps=N_STEPS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast generation failed: {e}")

    return {
        "start_time": start_time.isoformat(),
        "horizon_steps": N_STEPS,
        "interval_minutes": 10,
        "forecast": [
            {
                "datetime": ts.isoformat(),
                **{target: round(float(row[target]), 2) for target in TARGETS},
            }
            for ts, row in forecast_df.iterrows()
        ],
    }


@app.get("/context")
def get_context():
    """
    Returns weather (temperature, humidity, cloud cover) and localized holiday
    data for the same 24-hour forecast period, to support frontend visualizations.
    """
    try:
        start_time = _get_forecast_start_time()
        weather_df = get_weather_for_horizon(start_time, n_steps=N_STEPS)
        holiday_df = get_holiday_flags(pd.date_range(start_time, periods=N_STEPS, freq="10min"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context fetch failed: {e}")

    weather_records = [
        {
            "datetime": row["datetime"].isoformat(),
            "temperature_c": round(float(row["Temperature"]), 1),
            "humidity_pct": round(float(row["Humidity"]), 1),
            "cloud_cover_pct": round(float(row["cloud_cover"]), 1),
            "wind_speed_mps": round(float(row["WindSpeed_real"]), 2),  # ✅ ADD THIS
        }
        for _, row in weather_df.iterrows()
    ]

    holidays_in_period = holiday_df[holiday_df["is_holiday"] == 1]
    holiday_records = [
        {"datetime": row["datetime"].isoformat(), "holiday_name": row["holiday_name"]}
        for _, row in holidays_in_period.iterrows()
    ]

    return {
        "start_time": start_time.isoformat(),
        "horizon_steps": N_STEPS,
        "weather": weather_records,
        "holidays": holiday_records,
    }
