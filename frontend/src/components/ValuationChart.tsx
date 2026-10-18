export type ValuationPoint = {
  id: number;
  estimated_value: number;
  valuation_method: string;
  source: string | null;
  confidence: number | null;
  valuation_date: string;
};

function formatINR(n: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function ValuationChart({
  valuations,
}: {
  valuations: ValuationPoint[];
}) {
  if (!valuations.length) {
    return <p className="muted">No valuation records yet.</p>;
  }

  const data = [...valuations]
    .sort(
      (a, b) =>
        new Date(a.valuation_date).getTime() -
        new Date(b.valuation_date).getTime(),
    )
    .map((v) => ({
      id: v.id,
      date: String(v.valuation_date).slice(0, 10),
      value: Number(v.estimated_value),
      method: v.valuation_method,
      source: v.source ?? "",
      confidence:
        v.confidence != null
          ? `${Math.round(Number(v.confidence) * 100)}%`
          : "—",
    }));

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = max === min ? max * 0.1 || 1 : (max - min) * 0.12;
  const y0 = min - pad;
  const y1 = max + pad;
  const w = 640;
  const h = 220;
  const left = 48;
  const right = 16;
  const top = 16;
  const bottom = 36;
  const plotW = w - left - right;
  const plotH = h - top - bottom;

  const pts = data.map((d, i) => {
    const x =
      left + (data.length === 1 ? plotW / 2 : (i / (data.length - 1)) * plotW);
    const y = top + plotH - ((d.value - y0) / (y1 - y0)) * plotH;
    return { x, y, ...d };
  });
  const polyline = pts.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="valuation-chart-wrap">
      <div className="valuation-chart">
        <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="260" role="img" aria-label="Valuation history">
          <line x1={left} y1={top} x2={left} y2={top + plotH} stroke="#d8d0c3" />
          <line x1={left} y1={top + plotH} x2={left + plotW} y2={top + plotH} stroke="#d8d0c3" />
          {[0, 0.5, 1].map((t) => {
            const y = top + plotH - t * plotH;
            const val = y0 + t * (y1 - y0);
            return (
              <g key={t}>
                <line x1={left} y1={y} x2={left + plotW} y2={y} stroke="#e8e1d4" strokeDasharray="4 4" />
                <text x={left - 6} y={y + 4} textAnchor="end" fontSize="11" fill="#6d665c">
                  {val >= 1e7
                    ? `${(val / 1e7).toFixed(1)}Cr`
                    : val >= 1e5
                      ? `${(val / 1e5).toFixed(1)}L`
                      : Math.round(val).toLocaleString("en-IN")}
                </text>
              </g>
            );
          })}
          <polyline fill="none" stroke="#1c3a2e" strokeWidth="2.5" points={polyline} />
          {pts.map((p) => (
            <g key={p.id}>
              <circle cx={p.x} cy={p.y} r="4.5" fill="#1c3a2e" />
              <text x={p.x} y={h - 12} textAnchor="middle" fontSize="11" fill="#6d665c">
                {p.date.slice(5)}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <table className="valuation-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Estimate</th>
            <th>Method</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {[...data].reverse().map((row) => (
            <tr key={row.id}>
              <td>{row.date}</td>
              <td>{formatINR(row.value)}</td>
              <td>
                {row.method}
                {row.source ? ` · ${row.source}` : ""}
              </td>
              <td>{row.confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
