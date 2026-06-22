"""
Recursive 24-hour (144-step) forecasting logic.
Loads trained LightGBM models + history seed, and generates forecasts using
real calendar/holiday/live-weather features for the actual forecast period,
with lag/rolling features seeded from the historical data tail (see README
for the documented design rationale behind this choice).
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

from app.holidays_calendar import get_holiday_flags

MODELS_DIR = Path(__file__).parent.parent / "models"

TARGETS = joblib.load(MODELS_DIR / "targets.pkl")
FEATURE_COLS_PER_TARGET = joblib.load(MODELS_DIR / "feature_cols_per_target.pkl")
MODELS = {t: joblib.load(MODELS_DIR / f"model_{t}.pkl") for t in TARGETS}
HISTORY_SEED = pd.read_csv(MODELS_DIR / "history_seed.csv", parse_dates=["Datetime"]).set_index("Datetime")

N_STEPS = 144  # 24 hours at 10-minute resolution


def _build_calendar_features(next_time: pd.Timestamp) -> dict:
    """Recomputes all calendar/cyclical features for a single new timestamp."""
    hour, minute = next_time.hour, next_time.minute
    tfrac = hour + minute / 60.0
    dow = next_time.dayofweek
    month = next_time.month

    return {
        "hour": hour, "minute": minute,
        "hour_sin": np.sin(2 * np.pi * tfrac / 24),
        "hour_cos": np.cos(2 * np.pi * tfrac / 24),
        "dayofweek": dow,
        "dow_sin": np.sin(2 * np.pi * dow / 7),
        "dow_cos": np.cos(2 * np.pi * dow / 7),
        "is_weekend": int(dow >= 5),
        "is_sunday": int(dow == 6),
        "month": month,
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
        "block_of_day": hour * 6 + minute // 10,
    }


def _build_lag_roll_features(target: str, history: pd.DataFrame) -> dict:
    """Recomputes lag + rolling features for `target` from the running history."""
    series = history[target]
    feats = {
        f"{target}_lag_1": series.iloc[-1],
        f"{target}_lag_6": series.iloc[-6] if len(series) >= 6 else np.nan,
        f"{target}_lag_144": series.iloc[-144] if len(series) >= 144 else np.nan,
        f"{target}_lag_288": series.iloc[-288] if len(series) >= 288 else np.nan,
        f"{target}_lag_1008": series.iloc[-1008] if len(series) >= 1008 else np.nan,
        f"{target}_roll_1h_mean": series.iloc[-6:].mean(),
        f"{target}_roll_1h_std": series.iloc[-6:].std(),
        f"{target}_roll_6h_mean": series.iloc[-36:].mean(),
        f"{target}_roll_6h_std": series.iloc[-36:].std(),
        f"{target}_roll_24h_mean": series.iloc[-144:].mean(),
        f"{target}_roll_24h_std": series.iloc[-144:].std(),
    }
    return feats


def generate_forecast(start_time: pd.Timestamp, weather_df: pd.DataFrame, n_steps: int = N_STEPS) -> pd.DataFrame:
    """
    Generates a recursive n_steps-ahead forecast for ALL targets simultaneously.

    `weather_df` must have columns [datetime, Temperature, Humidity, cloud_cover, WindSpeed_real]
    aligned to the n_steps horizon starting at `start_time` (see app/weather.py).

    Returns a DataFrame indexed by datetime with one forecast column per target.
    """
    # Each target keeps its own running history (starts identical, diverges as
    # each target's own lag/roll features are updated independently)
    histories = {t: HISTORY_SEED.copy() for t in TARGETS}

    holiday_flags = get_holiday_flags(pd.date_range(start_time, periods=n_steps, freq="10min"))
    holiday_flags = holiday_flags.set_index("datetime")

    weather_df = weather_df.set_index("datetime")

    results = {t: [] for t in TARGETS}
    timestamps = []

    current_time = start_time
    for step in range(n_steps):
        next_time = current_time + pd.Timedelta(minutes=10) if step > 0 else start_time
        timestamps.append(next_time)

        calendar_feats = _build_calendar_features(next_time)

        # Weather + holiday features for this exact step (real data, not carried over)
        weather_row = weather_df.loc[next_time] if next_time in weather_df.index else weather_df.iloc[
            weather_df.index.get_indexer([next_time], method="nearest")[0]
        ]
        holiday_row = holiday_flags.loc[next_time]

        is_fan_on = int(weather_row.get("WindSpeed_real", 0) > 2.5)
        temperature = weather_row["Temperature"]
        cooling_degree = max(0.0, temperature - 22)
        temp_sq = temperature ** 2

        # Cloud cover comes from Open-Meteo's "cloud_cover" (0-100%); renamed to
        # match the training feature name "CloudCover", plus its interaction term.
        cloud_cover = weather_row["cloud_cover"]
        cloud_temp_interaction = cloud_cover * temperature

        shared_feats = {
            **calendar_feats,
            "Temperature": temperature,
            "Humidity": weather_row["Humidity"],
            "is_fan_on": is_fan_on,
            "cooling_degree": cooling_degree,
            "temp_sq": temp_sq,
            "CloudCover": cloud_cover,
            "cloud_temp_interaction": cloud_temp_interaction,
            "is_holiday": holiday_row["is_holiday"],
            "is_pre_holiday": holiday_row["is_pre_holiday"],
            "is_post_holiday": holiday_row["is_post_holiday"],
            "days_to_nearest_holiday": holiday_row["days_to_nearest_holiday"],
        }

        for target in TARGETS:
            history = histories[target]
            lag_roll_feats = _build_lag_roll_features(target, history)

            row_feats = {**shared_feats, **lag_roll_feats}
            feature_cols = FEATURE_COLS_PER_TARGET[target]
            X_next = pd.DataFrame([row_feats])[feature_cols]

            y_next = MODELS[target].predict(X_next)[0]
            results[target].append(y_next)

            new_row = pd.DataFrame([{**row_feats, target: y_next}], index=[next_time])
            histories[target] = pd.concat([history, new_row])

        current_time = next_time

    forecast_df = pd.DataFrame(results, index=pd.DatetimeIndex(timestamps, name="datetime"))
    return forecast_df