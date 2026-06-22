"""
Localized Dhanbad/Jharkhand holiday calendar for the LIVE prediction period.
Combines library-computed lunar/national holidays (Jharkhand subdivision) with
hyperlocal tribal/regional holidays sourced from the BBMKU Dhanbad University list.
"""
import pandas as pd
import holidays
from functools import lru_cache

# Fixed-date and lunar-estimated hyperlocal holidays, sourced from the BBMKU
# Dhanbad University 2025 list. Month/day reused for fixed-date entries;
# lunar entries are estimated per-year (see notebook for methodology/confidence notes).
MANUAL_HOLIDAYS_BY_YEAR = {
    2026: {
        "2026-01-16": "Tusu Parab",
        "2026-02-11": "Mage Parab",
        "2026-03-21": "Sarhul",
        "2026-06-25": "Rath Yatra",
        "2026-06-30": "Hul Diwas",
        "2026-08-16": "Mansha Puja",
        "2026-09-12": "Teej Parab",
        "2026-09-17": "Vishwakarma Puja",
        "2026-09-22": "Karma Puja",
        "2026-09-30": "Jivitputrika Parab",
        "2026-11-09": "Sohrai",
    }
}


@lru_cache(maxsize=8)
def get_holiday_calendar(year: int) -> pd.DataFrame:
    """Returns a DataFrame of date -> holiday_name for the given year."""
    jh_holidays = holidays.India(years=year, subdiv="JH", categories=("public", "optional"))
    lib_holidays = {pd.to_datetime(d): name for d, name in jh_holidays.items()}

    manual = MANUAL_HOLIDAYS_BY_YEAR.get(year, {})
    manual_holidays = {pd.to_datetime(d): name for d, name in manual.items()}

    combined = {**lib_holidays, **manual_holidays}
    calendar_df = pd.DataFrame(
        [(d, name) for d, name in combined.items()], columns=["date", "holiday_name"]
    ).sort_values("date").reset_index(drop=True)
    return calendar_df


def get_holiday_flags(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Given a DatetimeIndex (e.g. the 144-step forecast horizon), returns
    is_holiday / is_pre_holiday / is_post_holiday / days_to_nearest_holiday
    for each timestamp, plus the holiday name if applicable.
    """
    years_needed = sorted(set(dates.year))
    calendars = [get_holiday_calendar(y) for y in years_needed]
    full_calendar = pd.concat(calendars, ignore_index=True)
    holiday_dates = set(pd.to_datetime(full_calendar["date"]).dt.normalize())
    holiday_name_map = dict(zip(
        pd.to_datetime(full_calendar["date"]).dt.normalize(), full_calendar["holiday_name"]
    ))

    holiday_arr = pd.to_datetime(sorted(holiday_dates))

    rows = []
    for ts in dates:
        d = ts.normalize()
        is_holiday = d in holiday_dates
        is_pre = (d + pd.Timedelta(days=1)) in holiday_dates
        is_post = (d - pd.Timedelta(days=1)) in holiday_dates
        days_to_nearest = int(min(abs((holiday_arr - d).days))) if len(holiday_arr) else None
        rows.append({
            "datetime": ts,
            "is_holiday": int(is_holiday),
            "is_pre_holiday": int(is_pre),
            "is_post_holiday": int(is_post),
            "days_to_nearest_holiday": days_to_nearest,
            "holiday_name": holiday_name_map.get(d, None),
        })
    return pd.DataFrame(rows)
