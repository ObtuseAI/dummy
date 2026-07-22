import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function RepoHarvester() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/repo-harvester/status').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Repo Harvester</h1>

      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Stored/local status only. Missing runtime evidence is UNKNOWN, never assumed idle. Source: {String(data.source ?? 'UNKNOWN')} · Status: {String(data.data_status ?? 'UNKNOWN')}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="Harvester Status" value={data.status ?? 'UNKNOWN'} />
        <Card label="Kill Switch" value={data.kill_switch_active == null ? 'UNKNOWN' : data.kill_switch_active ? 'ACTIVE' : 'INACTIVE'} />
        <Card label="Emergency Stop" value={data.emergency_stop_active == null ? 'UNKNOWN' : data.emergency_stop_active ? 'ACTIVE' : 'INACTIVE'} />
      </div>

      <Section title="Data Availability">
        <p className="text-sm text-gray-400">
          This endpoint currently reports harvester status only. Scan counts, adapter verdicts, firewall state,
          and findings are UNKNOWN until the backend exposes those fields from a verified artifact.
        </p>
      </Section>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-4 bg-gray-800 rounded">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xl font-bold">{String(value ?? 'UNKNOWN')}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
    </div>
  );
}
