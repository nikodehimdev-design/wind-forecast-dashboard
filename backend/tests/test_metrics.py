import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.services.metrics import (
    build_evaluation,
    calculate_metrics,
    prepare_actuals,
    select_day_ahead_forecasts,
)
from app.routers.forecast import interval_coverage, sum_mwh
from app.services.forecast_archive import (
    archive_status,
    load_forecasts,
    store_forecasts,
)
from app.services.elexon import fetch_archived_forecasts, fetch_forecasts


class MetricsTests(unittest.TestCase):
    def test_actuals_remain_half_hourly(self):
        actuals = pd.DataFrame({
            "startTime": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:30:00Z",
            ],
            "actual": [100, 120],
        })

        prepared = prepare_actuals(actuals)

        self.assertEqual(len(prepared), 2)
        self.assertEqual(
            prepared["startTime"].dt.minute.tolist(),
            [0, 30],
        )

    def test_latest_forecast_before_cutoff_is_selected_per_interval(self):
        forecasts = pd.DataFrame({
            "startTime": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:30:00Z",
            ],
            "publishTime": [
                "2026-01-01T15:00:00Z",
                "2026-01-01T17:00:00Z",
                "2026-01-01T17:30:00Z",
                "2026-01-01T16:30:00Z",
            ],
            "forecast": [90, 95, 105, 115],
        })

        selected = select_day_ahead_forecasts(forecasts, cutoff_hour=17)

        self.assertEqual(selected["forecast"].tolist(), [95, 115])
        self.assertEqual(
            selected["startTime"].dt.minute.tolist(),
            [0, 30],
        )

    def test_metrics_use_only_matched_half_hour_intervals(self):
        actuals = pd.DataFrame({
            "startTime": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:30:00Z",
            ],
            "actual": [100, 120],
        })
        forecasts = pd.DataFrame({
            "startTime": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:30:00Z",
            ],
            "publishTime": [
                "2026-01-01T16:00:00Z",
                "2026-01-01T16:00:00Z",
            ],
            "forecast": [110, 100],
        })

        evaluation = build_evaluation(actuals, forecasts)
        metrics = calculate_metrics(evaluation)

        self.assertEqual(metrics["count"], 2)
        self.assertEqual(metrics["mae"], 15.0)
        self.assertEqual(metrics["rmse"], 15.811)
        self.assertEqual(metrics["bias"], -5.0)
        self.assertEqual(metrics["mape"], 13.333)

    def test_energy_sums_half_hourly_power_as_half_hour_mwh(self):
        readings = pd.DataFrame({"actual": [100.0, 200.0]})

        self.assertEqual(sum_mwh(readings, "actual"), 150.0)

    def test_interval_coverage_reports_source_range(self):
        readings = pd.DataFrame({
            "startTime": pd.to_datetime([
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:30:00Z",
                "2026-01-02T01:00:00Z",
            ]),
            "actual": [100.0, None, 120.0],
        })

        self.assertEqual(
            interval_coverage(readings, "actual"),
            {
                "intervals": 2,
                "from": "2026-01-02T00:00:00+00:00",
                "to": "2026-01-02T01:00:00+00:00",
            },
        )

    def test_forecast_archive_keeps_publication_vintages_by_delivery_interval(self):
        forecasts = pd.DataFrame({
            "startTime": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-01-03T00:00:00Z",
            ],
            "publishTime": [
                "2026-01-01T15:00:00Z",
                "2026-01-01T16:00:00Z",
                "2026-01-02T15:00:00Z",
            ],
            "generation": [100, 110, 120],
        })

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecasts.sqlite3"
            self.assertEqual(store_forecasts(forecasts, path), 3)
            stored = load_forecasts(
                pd.Timestamp("2026-01-02T00:00:00Z"),
                pd.Timestamp("2026-01-03T00:00:00Z"),
                path,
            )
            status = archive_status(path)

        self.assertEqual(stored["generation"].tolist(), [100, 110])
        self.assertEqual(status["forecast_records"], 3)
        self.assertIsNotNone(status["last_captured_at"])

    def test_forecast_fetch_uses_archived_vintages_for_historical_period(self):
        historical = pd.DataFrame({
            "startTime": ["2026-01-02T00:00:00Z"],
            "publishTime": ["2026-01-01T16:00:00Z"],
            "generation": [100],
        })
        current_stream = [{
            "startTime": "2026-10-29T00:00:00Z",
            "publishTime": "2026-10-28T16:00:00Z",
            "generation": 120,
        }]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecasts.sqlite3"
            with patch.dict(os.environ, {"WIND_FORECAST_DB_PATH": str(path)}):
                store_forecasts(historical)
                with patch("app.services.elexon.get_records", return_value=current_stream):
                    with patch(
                        "app.services.elexon.get_dataset_records",
                        return_value=[],
                    ):
                        fetched = fetch_forecasts(
                            pd.Timestamp("2026-01-02T00:00:00Z").to_pydatetime(),
                            pd.Timestamp("2026-01-03T00:00:00Z").to_pydatetime(),
                        )

        self.assertEqual(fetched["generation"].tolist(), [100])
        self.assertEqual(fetched["publishTime"].dt.hour.tolist(), [16])

    def test_historical_archive_requests_are_split_into_max_seven_day_windows(self):
        response = [{
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-01T16:00:00Z",
            "generation": 100,
        }]

        with patch(
            "app.services.elexon.get_dataset_records",
            return_value=response,
        ) as get_records:
            fetched = fetch_archived_forecasts(
                pd.Timestamp("2026-01-01T00:00:00Z").to_pydatetime(),
                pd.Timestamp("2026-01-09T00:00:00Z").to_pydatetime(),
            )

        self.assertEqual(get_records.call_count, 2)
        first_params = get_records.call_args_list[0].args[1]
        second_params = get_records.call_args_list[1].args[1]
        first_end = pd.Timestamp(first_params["PublishDateTimeTo"])
        second_start = pd.Timestamp(second_params["PublishDateTimeFrom"])
        self.assertEqual(second_start - first_end, pd.Timedelta(seconds=1))
        self.assertEqual(len(fetched), 1)


if __name__ == "__main__":
    unittest.main()
