from contextlib import closing
import os
import sqlite3
from pathlib import Path

import pandas as pd


FORECAST_COLUMNS = ["startTime", "publishTime", "generation"]
DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "wind_forecasts.sqlite3"
)


def database_path() -> Path:
    return Path(os.getenv("WIND_FORECAST_DB_PATH", str(DEFAULT_DB_PATH)))


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS forecasts (
            start_time TEXT NOT NULL,
            publish_time TEXT NOT NULL,
            generation REAL NOT NULL,
            captured_at TEXT NOT NULL,
            PRIMARY KEY (start_time, publish_time)
        )
        """
    )
    return connection


def _timestamp_key(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def store_forecasts(
    forecasts: pd.DataFrame,
    db_path: Path | None = None,
) -> int:
    if forecasts is None or forecasts.empty:
        return 0

    missing = set(FORECAST_COLUMNS) - set(forecasts.columns)
    if missing:
        raise ValueError(f"Forecast archive is missing columns: {sorted(missing)}")

    frame = forecasts[FORECAST_COLUMNS].copy()
    frame["startTime"] = pd.to_datetime(frame["startTime"], utc=True, errors="coerce")
    frame["publishTime"] = pd.to_datetime(frame["publishTime"], utc=True, errors="coerce")
    frame["generation"] = pd.to_numeric(frame["generation"], errors="coerce")
    frame = frame.dropna(subset=FORECAST_COLUMNS)
    if frame.empty:
        return 0

    captured_at = pd.Timestamp.now(tz="UTC").isoformat().replace("+00:00", "Z")
    records = [
        (
            _timestamp_key(start_time),
            _timestamp_key(publish_time),
            float(generation),
            captured_at,
        )
        for start_time, publish_time, generation in frame.itertuples(
            index=False, name=None
        )
    ]

    with closing(_connect(db_path or database_path())) as connection:
        with connection:
            connection.executemany(
                """
                INSERT INTO forecasts (start_time, publish_time, generation, captured_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(start_time, publish_time) DO UPDATE SET
                    generation = excluded.generation,
                    captured_at = excluded.captured_at
                """,
                records,
            )

    return len(records)


def load_forecasts(
    start: pd.Timestamp,
    end: pd.Timestamp,
    db_path: Path | None = None,
) -> pd.DataFrame:
    path = db_path or database_path()
    if not path.exists():
        return pd.DataFrame(columns=FORECAST_COLUMNS)

    start_utc = _timestamp_key(pd.to_datetime(start, utc=True))
    end_utc = _timestamp_key(pd.to_datetime(end, utc=True))
    with closing(sqlite3.connect(path, timeout=30)) as connection:
        frame = pd.read_sql_query(
            """
            SELECT start_time AS startTime,
                   publish_time AS publishTime,
                   generation
            FROM forecasts
            WHERE start_time >= ? AND start_time < ?
            ORDER BY start_time, publish_time
            """,
            connection,
            params=(start_utc, end_utc),
        )

    for column in ("startTime", "publishTime"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def archive_status(db_path: Path | None = None) -> dict:
    path = db_path or database_path()
    if not path.exists():
        return {"forecast_records": 0, "last_captured_at": None}

    with closing(sqlite3.connect(path, timeout=30)) as connection:
        row = connection.execute(
            "SELECT COUNT(*), MAX(captured_at) FROM forecasts"
        ).fetchone()

    return {
        "forecast_records": int(row[0]),
        "last_captured_at": row[1],
    }
