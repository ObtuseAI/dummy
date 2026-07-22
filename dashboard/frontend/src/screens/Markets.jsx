import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function Markets() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/markets').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Markets unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;
  const allowed = Array.isArray(data.allowed_markets) ? data.allowed_markets : null;
  const blocked = Array.isArray(data.blocked_categories) ? data.blocked_categories : null;
  const categories = Array.isArray(data.market_categories) ? data.market_categories : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Markets</h1>
      <div className="rounded border-2 border-cyan-500 bg-cyan-950/60 p-4 text-cyan-100">
        <div className="text-lg font-black uppercase">{valueOrUnknown(data.data_status)}</div>
        <p className="mt-1 font-semibold">Configuration only — this is not a current market list or live broker snapshot.</p>
        <div className="mt-2 text-xs text-cyan-300">
          Live market snapshot: {booleanLabel(data.live_market_snapshot_available, 'AVAILABLE', 'NOT AVAILABLE')} · Source: {valueOrUnknown(data.source)}
        </div>
      </div>
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
        Weather and commodities are data-only context. They are not prediction, ranking, paper-trade, or execution targets.
      </div>
      <Section title="Allowed Markets">
        {allowed === null ? <Unknown /> : allowed.length ? (
          <ul className="list-disc pl-5 text-sm">{allowed.map(m => <li key={m}>{m}</li>)}</ul>
        ) : <p className="text-sm text-gray-400">No markets explicitly allowlisted in configuration</p>}
      </Section>
      <Section title="Blocked Categories">
        {blocked === null ? <Unknown /> : blocked.length ? (
          <ul className="list-disc pl-5 text-sm">{blocked.map(m => <li key={m}>{m}</li>)}</ul>
        ) : <p className="text-sm text-gray-400">No blocked categories recorded in configuration</p>}
      </Section>
      <Section title="Source Categories">
        {categories === null ? <Unknown /> : categories.length ? (
          <div className="flex flex-wrap gap-2">
            {categories.map(c => <span key={c} className="px-2 py-1 bg-gray-900 rounded text-sm">{c}</span>)}
          </div>
        ) : <p className="text-sm text-gray-400">No source categories recorded in configuration</p>}
      </Section>
    </div>
  );
}

function Unknown() {
  return <p className="text-sm font-semibold text-amber-300">UNKNOWN — source field unavailable</p>;
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
    </div>
  );
}
