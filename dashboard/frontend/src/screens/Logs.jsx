import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { valueOrUnknown } from '../components/TruthValue';

export default function Logs() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/logs').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Local logs unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading local log observations…</div>;
  const logs = Array.isArray(data.logs) ? data.logs : null;
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Local logs</h1>
      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Bounded local observations only. Source: {valueOrUnknown(data.source)} · Status: {valueOrUnknown(data.data_status)} · Malformed skipped: {valueOrUnknown(data.skipped_malformed)}
      </div>
      {logs === null ? (
        <p className="font-semibold text-amber-300">Log collection status: UNKNOWN — the local log source is missing or unreadable.</p>
      ) : logs.length ? (
        <div className="max-h-[40rem] space-y-2 overflow-y-auto">
          {logs.map((entry, index) => <pre key={index} className="overflow-x-auto rounded bg-gray-950 p-3 text-xs">{JSON.stringify(entry, null, 2)}</pre>)}
        </div>
      ) : <p className="text-gray-400">The verified local log file contains no entries in this bounded window.</p>}
    </div>
  );
}
