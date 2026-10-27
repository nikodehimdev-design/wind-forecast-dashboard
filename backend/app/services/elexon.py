from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
from app.services.forecast_archive import archive_status, load_forecasts, store_forecasts

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
TIMEOUT = 45

def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def get_records(
    dataset: str,
    start: datetime,
    end: datetime,
    query_params: dict[str, str] | None = None
):
    url = f"{BASE_URL}/datasets/{dataset}/stream"
    params = {"from": iso_utc(start), "to": iso_utc(end)}
    if query_params:
        params.update(query_params)
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    return records_from_payload(dataset, payload)


def get_dataset_records(dataset: str, query_params: dict[str, str]):
    url = f"{BASE_URL}/datasets/{dataset}"
    response = requests.get(url, params=query_params, timeout=TIMEOUT)
    response.raise_for_status()
    return records_from_payload(dataset, response.json())


def records_from_payload(dataset: str, payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "dataItems", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError(f"Unexpected {dataset} response format; expected a list of records.")

def fetch_actuals(start: datetime, end: datetime) -> pd.DataFrame:
    start_utc = pd.to_datetime(start, utc=True)
    end_utc = pd.to_datetime(end, utc=True)
    query_params = {
        "settlementDateFrom": (start_utc - pd.Timedelta(days=1)).date().isoformat(),
        "settlementDateTo": (end_utc + pd.Timedelta(days=1)).date().isoformat(),
        "fuelType": "WIND"
    }
    frame = pd.DataFrame(
        get_records("FUELHH", start, end, query_params=query_params)
    )
    if frame.empty:
        return pd.DataFrame(columns=["startTime", "actual"])
    fuel_col = "fuelType" if "fuelType" in frame else "fueltype" if "fueltype" in frame else None
    if fuel_col is None:
        raise ValueError("FUELHH response has no fuelType field.")
    frame = frame[frame[fuel_col].astype(str).str.upper() == "WIND"].copy()
    if not {"startTime", "generation"}.issubset(frame.columns):
        raise ValueError("FUELHH records need startTime and generation.")
    frame["startTime"] = pd.to_datetime(frame["startTime"], utc=True, errors="coerce")
    frame["generation"] = pd.to_numeric(frame["generation"], errors="coerce")
    frame = frame.dropna(subset=["startTime", "generation"])
    frame = frame[
        frame["startTime"].ge(start_utc) & frame["startTime"].lt(end_utc)
    ]
    return frame.groupby("startTime", as_index=False)["generation"].sum().rename(columns={"generation": "actual"})

def _normalize_forecasts(records) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty:
        return pd.DataFrame(columns=["startTime", "publishTime", "generation"])
    required = {"startTime", "publishTime", "generation"}
    if not required.issubset(frame.columns):
        raise ValueError(f"WINDFOR records must include {sorted(required)}.")
    frame["startTime"] = pd.to_datetime(frame["startTime"], utc=True, errors="coerce")
    frame["publishTime"] = pd.to_datetime(frame["publishTime"], utc=True, errors="coerce")
    frame["generation"] = pd.to_numeric(frame["generation"], errors="coerce")
    frame = frame.dropna(subset=["startTime", "publishTime", "generation"])
    return frame[["startTime", "publishTime", "generation"]]


def fetch_latest_forecasts(start: datetime, end: datetime) -> pd.DataFrame:
    # Include the preceding day because day-ahead forecasts are published
    # before the delivery date being evaluated.
    records = get_records("WINDFOR", start - timedelta(days=1), end)
    return _normalize_forecasts(records)


def fetch_archived_forecasts(start: datetime, end: datetime) -> pd.DataFrame:
    start_utc = pd.to_datetime(start, utc=True)
    end_utc = pd.to_datetime(end, utc=True)
    if end_utc <= start_utc:
        raise ValueError("Forecast archive end must be after start.")

    publish_start = start_utc.floor("D") - pd.Timedelta(days=1)
    last_delivery_day = (end_utc - pd.Timedelta(nanoseconds=1)).floor("D")
    publish_end = last_delivery_day - pd.Timedelta(days=1) + pd.Timedelta(
        hours=23, minutes=59, seconds=59
    )
    chunks = []
    chunk_start = publish_start

    while chunk_start <= publish_end:
        chunk_end = min(
            chunk_start + pd.Timedelta(days=7) - pd.Timedelta(seconds=1),
            publish_end,
        )
        records = get_dataset_records(
            "WINDFOR",
            {
                "PublishDateTimeFrom": iso_utc(chunk_start.to_pydatetime()),
                "PublishDateTimeTo": iso_utc(chunk_end.to_pydatetime()),
            },
        )
        chunk = _normalize_forecasts(records)
        if not chunk.empty:
            chunks.append(chunk)
        chunk_start = chunk_end + pd.Timedelta(seconds=1)

    if not chunks:
        return pd.DataFrame(columns=["startTime", "publishTime", "generation"])

    return (
        pd.concat(chunks, ignore_index=True)
        .drop_duplicates(subset=["startTime", "publishTime"], keep="last")
        .sort_values(["startTime", "publishTime"])
        .reset_index(drop=True)
    )


def capture_current_forecasts() -> int:
    now = datetime.now(timezone.utc)
    latest = fetch_latest_forecasts(
        now - timedelta(days=1),
        now + timedelta(days=7),
    )
    return store_forecasts(latest)


def fetch_forecasts(start: datetime, end: datetime) -> pd.DataFrame:
    latest = fetch_latest_forecasts(start, end)
    store_forecasts(latest)
    archived = fetch_archived_forecasts(start, end)
    store_forecasts(archived)

    start_utc = pd.to_datetime(start, utc=True)
    end_utc = pd.to_datetime(end, utc=True)
    stored = load_forecasts(start_utc, end_utc)
    frame = pd.concat([stored, archived, latest], ignore_index=True)
    frame = frame[
        frame["startTime"].ge(start_utc) & frame["startTime"].lt(end_utc)
    ]
    return _normalize_forecasts(
        frame.drop_duplicates(
            subset=["startTime", "publishTime"], keep="last"
        )
        .sort_values(["startTime", "publishTime"])
        .reset_index(drop=True)
    )


def get_forecast_archive_status() -> dict:
    return archive_status()
