import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import UtilizationBar from '../components/UtilizationBar';

export default function CapsExposure() {
  const [caps, setCaps] = useState(null);
  const [exposure, setExposure] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/api/read-only/caps')
      .then(setCaps)
      .catch(e => setError(e.message));
    fetchJson('/api/read-only/exposure')
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
        <Card label="Orders / rolling hour" value={exposure.orders_last_hour} />
        <Card label="State" value={exposure.state_status} />
      </div>

      {exposure.state_status !== 'ready' && (
        <div className="rounded border-2 border-red-600 bg-red-950/50 p-4 font-bold text-red-200">
          Exposure state unavailable — utilization is UNKNOWN and must not be treated as zero.
        </div>
      )}

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

      <Section title="Utilization">
        <div className="space-y-3">
          <UtilizationBar label="Total live exposure" value={exposure.total_exposure_cents} cap={capsData.max_total_live_exposure_cents} unit="¢" />
          <UtilizationBar label="Open markets" value={exposure.open_markets} cap={capsData.max_open_markets} />
          <UtilizationBar label="Orders submitted in rolling 60 minutes" value={exposure.orders_last_hour} cap={capsData.max_orders_per_hour} />
        </div>
        <div className="mt-2 text-xs text-gray-400">Hourly window: {exposure.orders_last_hour_window ?? 'UNKNOWN'} · Exposure source: {exposure.source ?? 'UNKNOWN'}</div>
      </Section>

      <Section title={`Positions (${Array.isArray(exposure.positions) ? exposure.positions.length : 'UNKNOWN'})`}>
        {!Array.isArray(exposure.positions) ? <UnknownCollection /> : exposure.positions.length ? (
          <JsonList items={exposure.positions} />
        ) : <p className="text-sm text-gray-400">No positions recorded in the durable local risk state</p>}
      </Section>

      <Section title={`Orders (${Array.isArray(exposure.orders) ? exposure.orders.length : 'UNKNOWN'})`}>
        {!Array.isArray(exposure.orders) ? <UnknownCollection /> : exposure.orders.length ? (
          <JsonList items={exposure.orders} />
        ) : <p className="text-sm text-gray-400">No open-order reservations recorded in the durable local risk state</p>}
      </Section>
    </div>
  );
}

function UnknownCollection() {
  return <p className="text-sm font-semibold text-amber-300">UNKNOWN — durable exposure state unavailable</p>;
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

function JsonList({ items }) {
  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {items.map((item, i) => (
        <pre key={i} className="bg-gray-900 p-2 rounded text-xs overflow-x-auto">{JSON.stringify(item, null, 2)}</pre>
      ))}
    </div>
  );
}
