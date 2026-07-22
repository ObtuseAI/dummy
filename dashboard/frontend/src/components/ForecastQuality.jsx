function finite(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function Sparkline({ values }) {
  const points = (values || []).map(finite).filter(value => value !== null);
  if (points.length < 2) return null;
  const low = Math.min(...points);
  const high = Math.max(...points);
  const range = high - low || 1;
  const path = points.map((value, index) => {
    const x = (index / (points.length - 1)) * 100;
    const y = 28 - ((value - low) / range) * 24;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg viewBox="0 0 100 32" className="h-10 w-32" role="img" aria-label="Forecast quality history">
      <polyline points={path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function ForecastQuality({ quality }) {
  if (!quality || typeof quality !== 'object') {
    return <div className="mt-2 rounded bg-gray-950 px-3 py-2 text-xs font-semibold text-amber-300">Forecast quality: UNKNOWN — no candidate-level evidence supplied.</div>;
  }
  const history = Array.isArray(quality.brier_history) ? quality.brier_history : [];
  return (
    <div className="mt-2 flex flex-wrap items-center gap-3 rounded bg-gray-950 px-3 py-2 text-xs text-gray-300">
      <span>Brier: {quality.brier_score ?? 'UNKNOWN'}</span>
      <span>Calibration: {quality.calibration_error ?? 'UNKNOWN'}</span>
      <span>ROI: {quality.roi ?? 'UNKNOWN'}</span>
      <Sparkline values={history} />
    </div>
  );
}
