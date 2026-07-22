export default function UtilizationBar({ label, value, cap, unit = '' }) {
  const numericValue = Number(value);
  const numericCap = Number(cap);
  const known = Number.isFinite(numericValue) && Number.isFinite(numericCap) && numericCap > 0;
  const utilization = known ? Math.max(0, (numericValue / numericCap) * 100) : null;
  const width = utilization === null ? 0 : Math.min(100, utilization);
  const tone = utilization === null ? 'bg-gray-600' : utilization >= 90 ? 'bg-red-500' : utilization >= 70 ? 'bg-amber-400' : 'bg-emerald-500';
  return (
    <div className="rounded bg-gray-900 p-3 text-sm">
      <div className="flex justify-between gap-3">
        <span className="text-gray-300">{label}</span>
        <span className="font-mono">{known ? `${numericValue}${unit} / ${numericCap}${unit} (${utilization.toFixed(1)}%)` : 'UNKNOWN'}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded bg-gray-700">
        <div className={`h-full ${tone}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
