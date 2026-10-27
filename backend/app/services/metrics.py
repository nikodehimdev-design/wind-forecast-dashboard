
import pandas as pd
import numpy as np


def prepare_actuals(actuals: pd.DataFrame) -> pd.DataFrame:
    """Return national actual generation at the source's half-hourly resolution."""
    columns = ["startTime", "actual"]

    if actuals is None or actuals.empty:
        return pd.DataFrame(columns=columns)

    frame = actuals.copy()

    if "actual" not in frame.columns and "generation" in frame.columns:
        frame = frame.rename(columns={"generation": "actual"})

    required = {"startTime", "actual"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Actual data must contain {required}")

    frame["startTime"] = pd.to_datetime(
        frame["startTime"], utc=True, errors="coerce"
    )
    frame["actual"] = pd.to_numeric(
        frame["actual"], errors="coerce"
    )

    frame = frame.dropna(subset=["startTime", "actual"])

    return (
        frame.groupby("startTime", as_index=False)["actual"]
        .sum()
        .sort_values("startTime")
        .reset_index(drop=True)
    )


def select_day_ahead_forecasts(
    forecasts: pd.DataFrame,
    cutoff_hour: int = 17
) -> pd.DataFrame:
    """
    Select the latest forecast published by the specified UTC cutoff
    on the day before each delivery interval.
    """
    columns = ["startTime", "publishTime", "forecast"]

    if forecasts is None or forecasts.empty:
        return pd.DataFrame(columns=columns)

    if not 0 <= cutoff_hour <= 23:
        raise ValueError("cutoff_hour must be between 0 and 23")

    frame = forecasts.copy()

    if "forecast" not in frame.columns and "generation" in frame.columns:
        frame = frame.rename(columns={"generation": "forecast"})

    required = {"startTime", "publishTime", "forecast"}
    if not required.issubset(frame.columns):
        raise ValueError(
            f"Forecast data must contain {required}. "
            f"Received: {list(frame.columns)}"
        )

    frame["startTime"] = pd.to_datetime(
        frame["startTime"], utc=True, errors="coerce"
    )
    frame["publishTime"] = pd.to_datetime(
        frame["publishTime"], utc=True, errors="coerce"
    )
    frame["forecast"] = pd.to_numeric(
        frame["forecast"], errors="coerce"
    )

    frame = frame.dropna(
        subset=["startTime", "publishTime", "forecast"]
    )

    # Decision cutoff: previous UTC day at cutoff_hour.
    frame["cutoff"] = (
        frame["startTime"].dt.floor("D")
        - pd.Timedelta(days=1)
        + pd.to_timedelta(cutoff_hour, unit="h")
    )

    frame = frame[frame["publishTime"] <= frame["cutoff"]]

    if frame.empty:
        return pd.DataFrame(columns=columns)

    # Select the latest eligible publication for each delivery interval.
    frame = (
        frame.sort_values(["startTime", "publishTime"])
        .drop_duplicates(subset=["startTime"], keep="last")
    )

    return frame[columns].reset_index(drop=True)


def build_evaluation(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
    cutoff_hour: int = 17
) -> pd.DataFrame:
    """Return all periods, retaining nulls where data is unmatched."""
    actual_half_hourly = prepare_actuals(actuals)

    selected_forecasts = select_day_ahead_forecasts(
        forecasts,
        cutoff_hour=cutoff_hour
    )

    evaluation = pd.merge(
        actual_half_hourly,
        selected_forecasts,
        on="startTime",
        how="outer"
    )

    evaluation["error"] = (
        evaluation["forecast"] - evaluation["actual"]
    )

    return evaluation.sort_values("startTime").reset_index(drop=True)


def calculate_metrics(evaluation: pd.DataFrame) -> dict:
    """Calculate forecast accuracy only for matched observations."""
    empty_result = {
        "count": 0,
        "mae": None,
        "rmse": None,
        "bias": None,
        "mape": None
    }

    if evaluation is None or evaluation.empty:
        return empty_result

    if not {"actual", "forecast"}.issubset(evaluation.columns):
        return empty_result

    valid = evaluation.dropna(subset=["actual", "forecast"])

    if valid.empty:
        return empty_result

    actual = valid["actual"].astype(float).to_numpy()
    forecast = valid["forecast"].astype(float).to_numpy()

    error = forecast - actual

    nonzero_actual = actual != 0

    mape = None
    if nonzero_actual.any():
        mape = float(
            np.mean(
                np.abs(
                    error[nonzero_actual] / actual[nonzero_actual]
                )
            ) * 100
        )

    return {
        "count": int(len(valid)),
        "mae": round(float(np.mean(np.abs(error))), 3),
        "rmse": round(float(np.sqrt(np.mean(error ** 2))), 3),
        "bias": round(float(np.mean(error)), 3),
        "mape": round(mape, 3) if mape is not None else None
    }


def get_evaluation_diagnostics(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
    evaluation: pd.DataFrame,
    cutoff_hour: int = 17
) -> dict:
    """Summarize source coverage and forecast/actual matching."""
    actual_half_hourly = prepare_actuals(actuals)
    selected = select_day_ahead_forecasts(forecasts, cutoff_hour)

    matched = 0
    if not evaluation.empty:
        matched = int(
            evaluation.dropna(
                subset=["actual", "forecast"]
            ).shape[0]
        )

    def time_range(frame):
        if frame.empty or "startTime" not in frame.columns:
            return {"from": None, "to": None}

        times = pd.to_datetime(frame["startTime"], utc=True)

        return {
            "from": times.min().isoformat(),
            "to": times.max().isoformat()
        }

    return {
        "actual_interval_count": int(len(actual_half_hourly)),
        "eligible_forecast_count": int(len(selected)),
        "evaluation_row_count": int(len(evaluation)),
        "matched_intervals": matched,
        "actual_time_range": time_range(actual_half_hourly),
        "forecast_time_range": time_range(selected),
        "cutoff_hour_utc": cutoff_hour
    }
