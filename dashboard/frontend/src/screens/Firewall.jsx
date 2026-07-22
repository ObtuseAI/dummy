import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { valueOrUnknown } from '../components/TruthValue';

export default function Firewall() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/api/read-only/firewall/rejections').then(setData).catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Firewall history unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading local firewall observations…</div>;
  const reasons = Array.isArray(data.observed_reasons) ? data.observed_reasons : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Firewall rejection evidence</h1>
      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Local log-derived observations only. Absence of a rejection in this bounded window is not proof that an order was allowed or submitted.
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Observed rejections" value={data.observed_rejection_count} />
        <Card label="Firewall events scanned" value={data.firewall_events_scanned} />
        <Card label="Malformed rows skipped" value={data.skipped_malformed} />
        <Card label="Window" value={data.window} />
      </div>
      <Section title={`Structured rejection reasons (${reasons === null ? 'UNKNOWN' : reasons.length})`}>
        {reasons === null ? (
          <p className="text-sm font-semibold text-amber-300">UNKNOWN — local firewall log could not be verified.</p>
        ) : reasons.length ? (
          <div className="max-h-[32rem] space-y-2 overflow-y-auto">
            {reasons.map(item => (
              <div key={item.reason} className="flex justify-between rounded border-l-4 border-red-500 bg-gray-900 p-3 text-sm">
                <span>{valueOrUnknown(item.reason)}</span>
                <span className="font-mono">{valueOrUnknown(item.count)}</span>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No structured firewall rejection reasons were observed in this bounded log window.</p>}
        <div className="mt-3 text-xs text-gray-500">Source: {valueOrUnknown(data.source)} · Status: {valueOrUnknown(data.data_status)}</div>
      </Section>
    </div>
  );
}

function Card({ label, value }) {
  return <div className="rounded bg-gray-800 p-4"><div className="text-sm text-gray-400">{label}</div><div className="break-words text-xl font-bold">{String(valueOrUnknown(value))}</div></div>;
}

function Section({ title, children }) {
  return <div className="rounded bg-gray-800 p-4"><h2 className="mb-3 text-lg font-semibold">{title}</h2>{children}</div>;
}
