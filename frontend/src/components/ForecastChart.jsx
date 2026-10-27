import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
const shortTime = (value) => value ? new Date(value).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) : "";
export default function ForecastChart({ data, onSelect }) {
  const formatted = data.map((item) => ({ ...item, chartTime: shortTime(item.startTime) }));
  const tooltipContent = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    const item = payload[0].payload;
    return <div className="chart-tooltip">
      <strong>Delivery: {label} UTC</strong>
      <div>Forecast: {item.forecast == null ? "Unavailable" : `${Number(item.forecast).toLocaleString()} MW`}</div>
      {item.publishTime && <div>Published: {new Date(item.publishTime).toLocaleString("en-GB", { timeZone: "UTC" })} UTC</div>}
      <div>Actual: {item.actual == null ? "Unavailable" : `${Number(item.actual).toLocaleString()} MW`}</div>
    </div>;
  };
  return <div className="chart-wrap"><ResponsiveContainer width="100%" height={340}>
    <LineChart data={formatted} margin={{ top: 10, right: 20, left: 4, bottom: 8 }} onClick={(state) => { const item = state?.activePayload?.[0]?.payload; if (item && onSelect) onSelect(item.startTime); }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#253247"/><XAxis dataKey="chartTime" minTickGap={35} tick={{ fill: "#9aa9bd", fontSize: 11 }}/><YAxis tick={{ fill: "#9aa9bd", fontSize: 11 }} unit=" MW" width={76}/>
      <Tooltip content={tooltipContent}/>
      <Legend/><Line type="monotone" dataKey="forecast" name="Selected day-ahead forecast" stroke="#60a5fa" strokeWidth={2.4} dot={false} connectNulls={false}/><Line type="monotone" dataKey="actual" name="Actual generation" stroke="#34d399" strokeWidth={2.4} dot={false} connectNulls={false}/>
    </LineChart>
  </ResponsiveContainer><p className="chart-hint">Click a chart point to inspect forecast publication history for that delivery interval.</p></div>;
}
