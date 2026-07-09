import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Markets() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/markets').then(setData); }, []);
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Markets</h1>
      <Section title="Allowed Markets">
        {(data.allowed_markets || []).length ? (
          <ul className="list-disc pl-5 text-sm">{data.allowed_markets.map(m => <li key={m}>{m}</li>)}</ul>
        ) : <p className="text-sm text-gray-400">No markets explicitly allowlisted</p>}
      </Section>
      <Section title="Blocked Categories">
        {(data.blocked_categories || []).length ? (
          <ul className="list-disc pl-5 text-sm">{data.blocked_categories.map(m => <li key={m}>{m}</li>)}</ul>
        ) : <p className="text-sm text-gray-400">None</p>}
      </Section>
      <Section title="Source Categories">
        <div className="flex flex-wrap gap-2">
          {(data.market_categories || []).map(c => <span key={c} className="px-2 py-1 bg-gray-900 rounded text-sm">{c}</span>)}
        </div>
      </Section>
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
