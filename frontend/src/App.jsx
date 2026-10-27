import { useEffect, useState } from "react";
import { Activity, AlertCircle, CalendarDays, RefreshCw, Wind, Zap } from "lucide-react";
import { getAccuracy, getHistory, getOverview, getSeries } from "./services/api";
import KpiCard from "./components/KpiCard";
import ForecastChart from "./components/ForecastChart";

const fmt = (value, digits = 1) => value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toLocaleString("en-GB", { maximumFractionDigits: digits });
const formatMetric = (value) => value == null ? "N/A" : fmt(value);
const formatCoverageRange = (range) => {
  if (!range?.from || !range?.to) return "No readings in selected period";
  const format = (value) => new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC"
  });
  return `${format(range.from)} to ${format(range.to)} UTC`;
};

export default function App() {
  const [from, setFrom] = useState("2026-01-01");
  const [to, setTo] = useState("2026-01-31");
  const [cutoff, setCutoff] = useState("17");
  const [overview, setOverview] = useState(null);
  const [series, setSeries] = useState([]);
  const [accuracy, setAccuracy] = useState(null);
  const [history, setHistory] = useState([]);
  const [selectedTime, setSelectedTime] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const matchedIntervals = overview?.matched_intervals;
  const matchedIntervalsLabel = matchedIntervals == null
    ? "— matched intervals"
    : matchedIntervals === 0
      ? "No matched intervals"
      : `${fmt(matchedIntervals, 0)} matched intervals`;
  const forecastCoverage = overview?.forecast_intervals ?? 0;
  const actualCoverage = overview?.actual_intervals ?? 0;
  const latestForecastPublication = overview?.latest_forecast_publish_time
    ? `${new Date(overview.latest_forecast_publish_time).toISOString().replace("T", " ").slice(0, 16)} UTC`
    : "No eligible forecast publication returned";
  const archiveStatus = overview?.forecast_archive;
  const lastArchiveCapture = archiveStatus?.last_captured_at
    ? new Date(archiveStatus.last_captured_at).toLocaleString("en-GB", { timeZone: "UTC" }) + " UTC"
    : "Collector has not captured a forecast yet";
  const coverageMessage = actualCoverage === 0
    ? "No FUELHH actual readings were returned for the selected dates. Choose a period with actual-data coverage."
    : forecastCoverage === 0
      ? "Actual readings are available, but no WINDFOR forecasts passed the selected day-ahead cutoff. Accuracy metrics need forecast archives for these delivery dates."
      : "Both sources returned data, but there are no shared delivery intervals. Accuracy metrics use only exact matching start times.";
  const selectedSeries = series.filter((item) => {
    const timestamp = Date.parse(item.startTime);
    if (!Number.isFinite(timestamp)) return false;
    const deliveryDate = new Date(timestamp).toISOString().slice(0, 10);
    return deliveryDate >= from && deliveryDate <= to;
  });

  async function loadData() {
    if (from > to) { setError("Start date must be on or before end date."); return; }
    setLoading(true); setError(""); setHistory([]);
    try {
      const [o, s, a] = await Promise.all([
        getOverview(from, to, Number(cutoff)),
        getSeries(from, to, Number(cutoff)),
        getAccuracy(from, to, Number(cutoff))
      ]);
      setOverview(o); setSeries(s.data || []); setAccuracy(a); setSelectedTime("");
    } catch (err) {
      setError(err.message || "Unable to load data."); setOverview(null); setSeries([]); setAccuracy(null);
    } finally { setLoading(false); }
  }
  useEffect(() => { loadData(); }, []);

  async function inspectHistory(startTime) {
    if (!startTime) return;
    setSelectedTime(startTime); setHistory([]);
    try { const result = await getHistory(startTime); setHistory(result.history || []); }
    catch (err) { setError(`Could not load forecast history: ${err.message}`); }
  }

  return <main className="app-shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><Wind size={22}/></div><div><div className="brand-name">WIND<span>INTELLIGENCE</span></div><div className="brand-subtitle">Renewable generation · Forecast analytics</div></div></div><div className="top-status"><span className="status-dot"/> Elexon data source</div></header>
    <section className="hero"><div><div className="eyebrow"><Zap size={14}/> DAY-AHEAD PROCUREMENT SUPPORT</div><h1>Wind Forecast<br/><span>Performance Monitor</span></h1><p>Understand forecast reliability before making electricity procurement decisions.</p></div><div className="hero-symbol"><Wind size={76} strokeWidth={1.1}/></div></section>
    <section className="filters panel"><div className="section-heading"><div><h2>Analysis period</h2><p>Half-hourly GB wind generation · timestamps shown in UTC</p></div><button className="primary-button" onClick={loadData} disabled={loading}><RefreshCw size={16} className={loading ? "spin" : ""}/>{loading ? "Loading…" : "Refresh analysis"}</button></div>
      <div className="filter-grid"><label><span>From date</span><input type="date" value={from} onChange={(e) => setFrom(e.target.value)}/></label><label><span>To date</span><input type="date" value={to} onChange={(e) => setTo(e.target.value)}/></label><label><span>Day-ahead cutoff (UTC)</span><select value={cutoff} onChange={(e) => setCutoff(e.target.value)}><option value="12">12:00 UTC</option><option value="15">15:00 UTC</option><option value="17">17:00 UTC (assumption)</option><option value="18">18:00 UTC</option><option value="23">23:00 UTC</option></select></label></div>
      <div className="assumption-note"><AlertCircle size={15}/> A day-ahead forecast is the latest publication at or before the selected UTC cutoff on the preceding delivery day. Confirm this assumed cutoff with the client.</div>
    </section>
    {error && <div className="error-banner"><AlertCircle size={18}/><div><strong>Data request issue</strong><br/>{error}</div></div>}
    <section className="section-block"><div className="section-heading"><div><h2>Performance overview</h2><p>{overview?.period || `${from} to ${to}`} · Half-hourly matched forecast/actual intervals · Forecast cutoff {cutoff}:00 UTC previous day</p></div><span className="section-chip"><Activity size={14}/> {matchedIntervalsLabel}</span></div>
      <div className="kpi-grid"><KpiCard type="mae" label="Mean absolute error" value={formatMetric(overview?.mae)} unit={overview?.mae == null ? "" : " MW"} helper={overview?.mae == null ? "Needs matched forecast and actual data" : "Average absolute forecast error"}/><KpiCard type="rmse" label="Root mean squared error" value={formatMetric(overview?.rmse)} unit={overview?.rmse == null ? "" : " MW"} helper={overview?.rmse == null ? "Needs matched forecast and actual data" : "Penalizes larger errors"}/><KpiCard type="bias" label="Forecast bias" value={formatMetric(overview?.bias)} unit={overview?.bias == null ? "" : " MW"} helper={overview?.bias == null ? "Needs matched forecast and actual data" : "Positive = overforecasting"}/><KpiCard type="mape" label="Mean absolute percentage error" value={formatMetric(overview?.mape)} unit={overview?.mape == null ? "" : "%"} helper={overview?.mape == null ? "Needs matched nonzero actual data" : "Zero actual values excluded"}/></div>
      {overview && matchedIntervals === 0 && <div className="error-banner"><AlertCircle size={18}/><div><strong>Accuracy cannot be calculated for this period</strong><br/>{coverageMessage} The local Elexon archive currently contains {fmt(archiveStatus?.forecast_records, 0)} records; last captured: {lastArchiveCapture}. Forecasts captured from now on can support later evaluations, but cannot recreate missing January 2026 forecast vintages. No score is substituted or inferred.</div></div>}
    </section>
    <section className="section-block"><div className="section-heading"><div><h2>Data coverage</h2><p>Availability within the selected period · UTC</p></div></div>
      <div className="kpi-grid">
        <KpiCard type="mae" label="Actual intervals" value={fmt(overview?.coverage?.actual?.intervals ?? overview?.actual_intervals, 0)} helper={formatCoverageRange(overview?.coverage?.actual)}/>
        <KpiCard type="rmse" label="Eligible day-ahead forecasts" value={fmt(overview?.coverage?.forecast?.intervals ?? overview?.forecast_intervals, 0)} helper={formatCoverageRange(overview?.coverage?.forecast)}/>
        <KpiCard type="bias" label="Matched intervals" value={fmt(overview?.coverage?.matched?.intervals ?? matchedIntervals, 0)} helper={formatCoverageRange(overview?.coverage?.matched)}/>
        <KpiCard type="mape" label="Archived forecast records" value={fmt(archiveStatus?.forecast_records, 0)} helper={`Latest capture: ${lastArchiveCapture}`}/>
      </div>
    </section>
    <section className="section-block"><div className="section-heading"><div><h2>Actual generation</h2><p>Measured national wind output from FUELHH during the selected period</p></div><span className="section-chip">{fmt(overview?.actual_intervals, 0)} half-hour intervals</span></div>
      <div className="kpi-grid"><KpiCard type="mae" label="Average actual generation" value={formatMetric(overview?.average_actual_generation_mw)} unit={overview?.average_actual_generation_mw == null ? "" : " MW"} helper="Mean available half-hourly wind power"/><KpiCard type="rmse" label="Actual generation energy" value={formatMetric(overview?.total_actual_generation_mwh)} unit={overview?.total_actual_generation_mwh == null ? "" : " MWh"} helper="Half-hourly MW readings × 0.5 hours"/></div>
    </section>
    <section className="panel section-block"><div className="section-heading"><div><h2>Wind generation profile</h2><p>Latest forecast published by the configured day-ahead cutoff vs measured generation</p><p>Latest eligible publication in this period: {latestForecastPublication}</p></div><span className="unit-label">MW · half-hourly</span></div>
      {loading && selectedSeries.length === 0 ? <div className="empty-state">Loading Elexon data…</div> : selectedSeries.length ? <ForecastChart data={selectedSeries} onSelect={inspectHistory}/> : <div className="empty-state"><Wind size={28}/><strong>No chart data for the selected dates</strong><span>Change the date range or check API availability.</span></div>}
    </section>
    <section className="two-column section-block">
      <div className="panel"><div className="section-heading"><div><h2>Daily accuracy</h2><p>MAE by delivery day</p></div><CalendarDays size={18}/></div>
        {accuracy?.daily?.length ? <div className="table-scroll"><table><thead><tr><th>Date</th><th>Intervals</th><th>MAE (MW)</th><th>Bias (MW)</th></tr></thead><tbody>{accuracy.daily.map((row) => <tr key={row.date}><td>{row.date}</td><td>{row.count}</td><td>{fmt(row.mae)}</td><td className={row.bias > 0 ? "positive" : row.bias < 0 ? "negative" : ""}>{fmt(row.bias)}</td></tr>)}</tbody></table></div> : <div className="empty-state compact">Daily statistics will appear when matched data is available.</div>}
      </div>
      <div className="panel"><div className="section-heading"><div><h2>Forecast history</h2><p>{selectedTime ? `${new Date(selectedTime).toLocaleString("en-GB", { timeZone: "UTC" })} UTC` : "Click a chart point to inspect a delivery interval"}</p></div></div>
        {history.length ? <div className="table-scroll"><table><thead><tr><th>Published (UTC)</th><th>Forecast (MW)</th></tr></thead><tbody>{history.map((row) => <tr key={row.publishTime}><td>{new Date(row.publishTime).toLocaleString("en-GB", { timeZone: "UTC" })}</td><td>{fmt(row.generation)}</td></tr>)}</tbody></table></div> : <div className="empty-state compact">Publication history appears here after selecting a chart point.</div>}
      </div>
    </section>
    <section className="source-strip"><div><span className="source-icon"><Zap size={17}/></span><div><strong>Data provenance</strong><p>Actuals: FUELHH · Forecasts: WINDFOR · Elexon BMRS</p></div></div><div className="source-links"><a href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream" target="_blank" rel="noreferrer">Actuals API ↗</a><a href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream" target="_blank" rel="noreferrer">Forecast API ↗</a></div></section>
    <footer>WIND INTELLIGENCE <span>·</span> Pilot analytics dashboard <span>·</span> Validate API data before operational use</footer>
  </main>;
}
