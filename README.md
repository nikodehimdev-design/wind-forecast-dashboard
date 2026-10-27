# Wind Forecast Analytics Dashboard

Full-stack pilot app for UK wind generation forecast monitoring and accuracy analysis.

## Stack
- React + Vite + Recharts
- Python + FastAPI + Pandas + NumPy
- Docker Compose

## Data sources
- Actuals (filter `fuelType = WIND`): https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream
- Forecasts: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream
- Assignment analysis period: January 1–31, 2026 (the dashboard defaults to this month).

## Run with Docker
```bash
docker compose up --build
```
Frontend: http://localhost:5173  
API docs: http://localhost:8000/docs  
Health check: http://localhost:8000/api/health

Docker Compose also starts a forecast collector. It polls the Elexon WINDFOR stream every 15 minutes and stores publication vintages in a persistent SQLite volume shared with the API. The API also backfills historical WINDFOR records from Elexon's `/datasets/WINDFOR` endpoint, querying by publication-time windows of at most seven days. The collector builds an ongoing local archive; it is not a substitute for Elexon's historical dataset endpoint.

## Run without Docker
Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Frontend, in another terminal:
```bash
cd frontend
npm install
npm run dev
```
To archive WINDFOR publications when running without Docker, start a second backend terminal:
```bash
cd backend
# activate the backend virtual environment
python -m app.services.forecast_collector
```
The API also archives forecasts whenever it fetches them. Set `WIND_FORECAST_DB_PATH` to choose a different SQLite archive location; the default is `backend/data/wind_forecasts.sqlite3`.

## Endpoints
- `GET /api/health`
- `GET /api/forecast/overview?from=2026-01-01&to=2026-01-31&cutoff_hour=17`
- `GET /api/forecast/series?from=2026-01-01&to=2026-01-31&cutoff_hour=17`
- `GET /api/forecast/accuracy?from=2026-01-01&to=2026-01-31&cutoff_hour=17`
- `GET /api/forecast/history?start_time=2026-01-15T12:00:00Z`

## Assumptions and limitations
- Default cutoff is 17:00 UTC on the previous day. This is an explicit assumption; confirm the client's actual procurement deadline.
- All delivery timestamps and the decision cutoff use UTC. For each half-hour delivery interval, the selected forecast is the latest WINDFOR publication at or before the prior-day cutoff.
- FUELHH actuals are filtered to `fuelType = WIND`, requested by settlement-date bounds, and then filtered to the exact selected UTC range. Multiple records for the same delivery interval are summed.
- Actuals and forecasts are compared at the source's half-hourly `startTime`; no hourly rounding or interpolation is applied.
- Only intervals with both actual and eligible day-ahead forecast values are used for accuracy metrics. The live WINDFOR stream supplies the latest forecast horizon; historical publication vintages are retrieved from the Elexon `/datasets/WINDFOR` endpoint using `PublishDateTimeFrom` and `PublishDateTimeTo` in windows no longer than seven days.
- January 2026 historical WINDFOR vintages are retrieved from Elexon's `/datasets/WINDFOR` endpoint by publication time in seven-day chunks because the endpoint rejects larger ranges. A live verification returned 17,688 forecast vintage records for January delivery dates. With the 17:00 UTC previous-day cutoff, 744 forecast intervals matched FUELHH actuals exactly; no values are interpolated or synthesized. The sample accuracy scores were MAE 1,968.251 MW, RMSE 2,434.742 MW, bias +1,816.526 MW, and MAPE 18.338%. These figures describe the intervals returned in that verification and can change if Elexon revises or expands its historical data.
- MAPE excludes zero actual values.
- `generation` is treated as MW. Approximate energy is calculated as the sum of half-hourly MW × 0.5 hours. Coverage may be incomplete when source intervals are missing.
- This pilot uses national wind data only. It does not ingest consumer demand, calculate net shortfall, recommend thermal generation, or execute a market purchase.
- Validate Elexon data completeness, rate limits and historical publication availability before operational use.

## Project structure
```text
wind-forecast-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/forecast.py
│   │   └── services/{elexon.py,forecast_archive.py,forecast_collector.py,metrics.py}
│   ├── tests/test_metrics.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/{KpiCard.jsx,ForecastChart.jsx}
│   │   ├── services/api.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   └── nginx.conf
├── compose.yaml
├── .gitignore
└── README.md
```

## AI tools
AI assistance (Copilot SDK in VS Code) was used to develop and refine application code and documentation. The implementation and validation results should be reviewed by the project author before client or operational use.

## Assignment readiness and submission checklist

### Implemented in this workspace
- [x] React frontend and Python/FastAPI backend.
- [x] Docker Compose startup for the app and a WINDFOR collector with a persistent SQLite archive volume.
- [x] Elexon FUELHH national wind actuals and WINDFOR forecasts, half-hourly interval matching, publication-cutoff selection, and MAE/RMSE/bias/MAPE calculations.
- [x] January 2026 as the default analysis period, with actual and forecast coverage shown separately.
- [x] README documents project files, startup, assumptions, limitations, and AI assistance.

### Must be completed before submission
- [x] Resolve the January 2026 forecast archive blocker using Elexon's historical `/datasets/WINDFOR` endpoint. Verified 17,688 vintage records, 744 intervals eligible at the 17:00 UTC cutoff and matched to actuals, and calculated all four accuracy metrics from those matched pairs. No accuracy values are inferred for unmatched intervals.
- [ ] Run `docker compose up --build` on the intended host and verify the frontend, API, collector, and persistent archive all work together. The host must support a continuously running collector and persistent shared storage; a static frontend deployment alone is insufficient.
- [ ] Initialize a Git repository, publish it as a public GitHub repository with an anonymous repository name, and add its URL here.
- [ ] Deploy the application and add the public application URL here. Verify the deployed API uses the same durable forecast archive as the collector.
- [ ] Record and upload an unlisted YouTube video of no more than 10 minutes, then add its URL here.
- [ ] Submit the application, repository, and video links using the specified form. Open every URL in an incognito/private browser first to verify public access.

### Suggested video outline (10 minutes maximum)
**Part 1 — client presentation (0:00–5:00):**
1. (0:00–0:45) State the procurement decision problem: wind output is uncertain when day-ahead purchases are made.
2. (0:45–2:00) Demonstrate the January period selector, UTC decision cutoff, and latest eligible forecast publication.
3. (2:00–3:15) Show half-hourly forecast versus actual generation and explain the matched-interval count.
4. (3:15–4:15) Explain MAE, RMSE, bias, and MAPE as decision-support measures; do not present N/A as zero.
5. (4:15–5:00) State data coverage and explain that only exact forecast/actual timestamp matches are scored. Do not claim procurement recommendations: consumer demand is outside this pilot's data scope.

**Part 2 — technical review (5:00–10:00):**
1. (5:00–6:00) Show the React/Vite frontend, FastAPI backend, and Docker Compose services.
2. (6:00–7:15) Trace Elexon FUELHH/WINDFOR data through validation and half-hourly timestamp matching.
3. (7:15–8:15) Explain the prior-day publication cutoff and metric formulas.
4. (8:15–9:15) Explain the seven-day-paginated historical WINDFOR retrieval and the SQLite collector's role in capturing future vintages.
5. (9:15–10:00) Show backend tests, frontend build, API health endpoint, known limitations, and operational follow-ups.
