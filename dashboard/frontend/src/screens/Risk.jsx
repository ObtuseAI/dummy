import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import UtilizationBar from '../components/UtilizationBar';
import { valueOrUnknown } from '../components/TruthValue';

export default function Risk() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/risk').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Risk telemetry unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  const caps = data.caps && typeof data.caps === 'object' && !Array.isArray(data.caps) ? data.caps : null;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Risk & Caps</h1>
      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Stored local risk state and configuration only — not a current broker risk snapshot. Source: {valueOrUnknown(data.source)} · Status: {valueOrUnknown(data.data_status)}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {caps === null ? <div className="font-semibold text-amber-300">Caps: UNKNOWN</div> : Object.entries(caps).map(([k, v]) => (
          <div key={k} className="bg-gray-800 p-3 rounded text-sm">
            <div className="text-gray-400">{k}</div>
            <div className="font-mono">{String(valueOrUnknown(v))}</div>
          </div>
        ))}
      </div>
      <div className="bg-gray-800 p-4 rounded">
        <div className="text-gray-400">Daily Loss (¢)</div>
        <div className="text-xl font-bold">{String(valueOrUnknown(data.daily_loss_cents))}</div>
        <div className="mt-1 text-xs text-gray-500">Status: {valueOrUnknown(data.daily_loss_status)}</div>
      </div>
      <div className="space-y-3 rounded bg-gray-800 p-4">
        <h2 className="text-lg font-semibold">Current utilization</h2>
        <UtilizationBar label="Daily loss" value={data.daily_loss_cents} cap={caps?.max_daily_loss_cents} unit="¢" />
      </div>
    </div>
  );
}
