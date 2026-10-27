import { Activity, Gauge, Waves, TrendingDown } from "lucide-react";
const icons = { mae: Activity, rmse: Gauge, bias: Waves, mape: TrendingDown };
export default function KpiCard({ type, label, value, unit, helper }) {
  const Icon = icons[type] || Activity;
  return <article className="kpi-card"><div className="kpi-top"><span>{label}</span><span className="kpi-icon"><Icon size={18}/></span></div><div className="kpi-value">{value}<small>{unit || ""}</small></div><div className="kpi-helper">{helper}</div></article>;
}
