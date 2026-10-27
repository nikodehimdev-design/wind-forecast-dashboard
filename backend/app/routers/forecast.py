from datetime import date, datetime, time, timedelta, timezone
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from app.services.elexon import (
    fetch_actuals,
    fetch_forecasts,
    get_forecast_archive_status,
)
from app.services.metrics import calculate_metrics, build_evaluation

router = APIRouter(prefix="/forecast", tags=["forecast"])

def load_data(from_date: date, to_date: date, cutoff_hour: int):
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="'to' must be on or after 'from'.")
    if (to_date - from_date).days > 31:
        raise HTTPException(status_code=400, detail="Request a maximum of 32 days at a time.")
    start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    try:
        actuals = fetch_actuals(start, end)
        forecasts = fetch_forecasts(start, end)
        return build_evaluation(actuals, forecasts, cutoff_hour)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=(
            "Unable to retrieve/process Elexon data. Verify API parameters and schema. "
            + str(exc)[:250]
        )) from exc

def sum_mwh(frame, column):
    vals = frame[column].dropna() if column in frame else pd.Series(dtype=float)
    return round(float(vals.sum() * 0.5), 2) if not vals.empty else None

def interval_coverage(frame, column):
    if frame.empty or column not in frame or "startTime" not in frame:
        return {"intervals": 0, "from": None, "to": None}

    covered = frame.loc[frame[column].notna(), "startTime"].dropna()
    if covered.empty:
        return {"intervals": 0, "from": None, "to": None}

    return {
        "intervals": int(len(covered)),
        "from": pd.to_datetime(covered.min(), utc=True).isoformat(),
        "to": pd.to_datetime(covered.max(), utc=True).isoformat()
    }

@router.get("/overview")
def overview(
    from_date: date = Query(date(2026, 1, 1), alias="from"),
    to_date: date = Query(date(2026, 1, 31), alias="to"),
    cutoff_hour: int = Query(17, ge=0, le=23)
):
    frame = load_data(from_date, to_date, cutoff_hour)
    metrics = calculate_metrics(frame)
    actual_values = frame["actual"].dropna() if "actual" in frame else pd.Series(dtype=float)
    forecast_values = frame["forecast"].dropna() if "forecast" in frame else pd.Series(dtype=float)
    matched_frame = frame.dropna(subset=["actual", "forecast"]) if not frame.empty else frame
    latest_publish_time = (
        pd.to_datetime(frame["publishTime"], utc=True).max().isoformat()
        if "publishTime" in frame and frame["publishTime"].notna().any()
        else None
    )
    return {
        "period": f"{from_date.isoformat()} to {to_date.isoformat()}",
        "cutoff_hour_utc": cutoff_hour,
        "matched_intervals": metrics["count"],
        "forecast_intervals": int(len(forecast_values)),
        "actual_intervals": int(len(actual_values)),
        "coverage": {
            "actual": interval_coverage(frame, "actual"),
            "forecast": interval_coverage(frame, "forecast"),
            "matched": interval_coverage(matched_frame, "actual")
        },
        "forecast_archive": get_forecast_archive_status(),
        "latest_forecast_publish_time": latest_publish_time,
        "average_actual_generation_mw": (
            round(float(actual_values.mean()), 3)
            if not actual_values.empty else None
        ),
        "total_actual_generation_mwh": sum_mwh(frame, "actual"),
        "total_forecast_generation_mwh": sum_mwh(frame, "forecast"),
        **metrics
    }

@router.get("/series")
def series(
    from_date: date = Query(date(2026, 1, 1), alias="from"),
    to_date: date = Query(date(2026, 1, 31), alias="to"),
    cutoff_hour: int = Query(17, ge=0, le=23)
):
    frame = load_data(from_date, to_date, cutoff_hour).sort_values("startTime")
    frame = frame.astype(object).where(pd.notna(frame), None)
    records = frame.to_dict(orient="records")
    for row in records:
        for key, value in row.items():
            if isinstance(value, (pd.Timestamp, datetime)):
                row[key] = value.isoformat()
            elif hasattr(value, "item"):
                row[key] = value.item()
    return {"data": records, "cutoff_hour_utc": cutoff_hour}

@router.get("/accuracy")
def accuracy(
    from_date: date = Query(date(2026, 1, 1), alias="from"),
    to_date: date = Query(date(2026, 1, 31), alias="to"),
    cutoff_hour: int = Query(17, ge=0, le=23)
):
    frame = load_data(from_date, to_date, cutoff_hour)
    valid = frame.dropna(subset=["forecast", "actual"]) if not frame.empty else frame
    daily = []
    if not valid.empty:
        valid = valid.copy()
        valid["day"] = valid["startTime"].dt.strftime("%Y-%m-%d")
        for day, group in valid.groupby("day"):
            daily.append({"date": day, **calculate_metrics(group)})
    return {"metrics": calculate_metrics(frame), "daily": daily}

@router.get("/history")
def history(start_time: str = Query(..., description="ISO-8601 delivery timestamp")):
    try:
        target = pd.to_datetime(start_time, utc=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ISO-8601 start_time") from exc
    try:
        forecasts = fetch_forecasts(target.to_pydatetime(), (target + pd.Timedelta(minutes=30)).to_pydatetime())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Forecast history request failed: {str(exc)[:250]}") from exc
    if forecasts.empty:
        return {"startTime": target.isoformat(), "history": []}
    rows = forecasts[forecasts["startTime"] == target].sort_values("publishTime")
    return {"startTime": target.isoformat(), "history": [
        {"startTime": row.startTime.isoformat(), "publishTime": row.publishTime.isoformat(),
         "generation": float(row.generation)}
        for row in rows.itertuples()
    ]}
