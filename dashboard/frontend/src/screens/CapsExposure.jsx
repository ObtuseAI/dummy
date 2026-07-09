import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function CapsExposure() {
  const [caps, setCaps] = useState(null);
  const [exposure, setExposure] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/v3/caps')
      .then(setCaps)
      .catch(e => setError(e.message));
    fetchJson('/v3/exposure')
      .then(setExposure)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!caps || !exposure) return <div className="p-4">Loading...</div>;

  const capsData = caps.caps || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Caps & Exposure</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="Mode" value={exposure.mode} />
        <Card label="Total Exposure (¢)" value={exposure.total_exposure_cents} />
        <Card label="Open Markets" value={exposure.open_markets} />
        <Card label="Open Orders" value={exposure.open_order_count} />
      </div>

      <Section title="Caps">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
          {Object.entries(capsData).map(([k, v]) => (
            <div key={k} className="flex justify-between bg-gray-900 p-2 rounded">
              <span className="text-gray-400">{k}</span>
              <span className="font-mono">{String(v)}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 text-xs text-gray-400">Source: {caps.source}</div>
      </Section>

      <Section title={`Positions (${(exposure.positions || []).length})`}>
        {(exposure.positions || []).length ? (
          <JsonList items={exposure.positions} />
        ) : <p className="text-sm text-gray-400">No positions</p>}
      </Section>

      <Section title={`Orders (${(exposure.orders || []).length})`}>
        {(exposure.orders || []).length ? (
          <JsonList items={exposure.orders} />
        ) : <p className="text-sm text-gray-400">No orders</p>}
      </Section>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-4 bg-gray-800 rounded">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xl font-bold">{String(value ?? 0)}</div>
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

function JsonList({ items }) {
  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {items.map((item, i) => (
        <pre key={i} className="bg-gray-900 p-2 rounded text-xs overflow-x-auto">{JSON.stringify(item, null, 2)}</pre>
      ))}
    </div>
  );
}
