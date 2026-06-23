"""
Live weather fetching for Dhanbad, Jharkhand using the Open-Meteo API.
No API key required. Returns hourly forecast data which is then resampled
to 10-minute resolution (via interpolation) to match the model's training frequency.
"""
import requests
import pandas as pd
import numpy as np
import time  # ✅ added for caching

DHANBAD_LAT = 23.7957
DHANBAD_LON = 86.4304

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# ✅ simple in-memory cache
_cache = {
    "data": None,
    "timestamp": 0
}

CACHE_TTL = 600  # 10 minutes


def fetch_dhanbad_weather_forecast(n_days: int = 2) -> pd.DataFrame:
    """
    Fetches hourly weather forecast for Dhanbad and resamples to 10-minute
    resolution via linear interpolation, to match the model's training granularity.
    Returns columns: datetime, Temperature, Humidity, cloud_cover, WindSpeed (proxy)
    """
    global _cache

    # ✅ return cached data if still valid
    if _cache["data"] is not None and (time.time() - _cache["timestamp"] < CACHE_TTL):
        return _cache["data"]

    params = {
        "latitude": DHANBAD_LAT,
        "longitude": DHANBAD_LON,
        "hourly": "temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m",
        "timezone": "Asia/Kolkata",
        "forecast_days": n_days,
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()["hourly"]

        hourly_df = pd.DataFrame({
            "datetime": pd.to_datetime(data["time"]),
            "Temperature": data["temperature_2m"],
            "Humidity": data["relative_humidity_2m"],
            "cloud_cover": data["cloud_cover"],
            "WindSpeed_real": data["wind_speed_10m"],  # real wind, kept separate from is_fan_on proxy
        }).set_index("datetime")

        # Resample to 10-min resolution via linear interpolation
        ten_min_index = pd.date_range(hourly_df.index.min(), hourly_df.index.max(), freq="10min")
        weather_10min = hourly_df.reindex(hourly_df.index.union(ten_min_index)).interpolate(
            method="time"
        ).reindex(ten_min_index)

        result = weather_10min.reset_index().rename(columns={"index": "datetime"})

        # ✅ save to cache
        _cache["data"] = result
        _cache["timestamp"] = time.time()

        return result

    except Exception as e:
        # ✅ fallback: use cached data if API fails (e.g., 429)
        if _cache["data"] is not None:
            print("Using cached weather due to API error:", e)
            return _cache["data"]

        raise


def get_weather_for_horizon(start_time: pd.Timestamp, n_steps: int = 144) -> pd.DataFrame:
    """
    Returns weather data aligned to the exact 144-step (24h) forecast horizon
    starting at `start_time`, at 10-minute resolution.
    """
    forecast_df = fetch_dhanbad_weather_forecast(n_days=2)
    horizon_index = pd.date_range(start_time, periods=n_steps, freq="10min")

    aligned = forecast_df.set_index("datetime").reindex(horizon_index, method="nearest")
    aligned = aligned.reset_index().rename(columns={"index": "datetime"})
    return aligned