import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { valueOrUnknown } from '../components/TruthValue';

export default function Orders() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/api/read-only/kalshi/orders').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Orders unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;
  const orders = Array.isArray(data.orders) ? data.orders : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Orders</h1>
      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Durable local order reservations only — not a current broker account snapshot. Source: {valueOrUnknown(data.source)} · Status: {valueOrUnknown(data.data_status)}
      </div>
      {orders === null ? (
        <p className="font-semibold text-amber-300">Order collection status: UNKNOWN — durable exposure state unavailable.</p>
      ) : orders.length ? (
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-800">
            <tr><th className="p-2">ID</th><th className="p-2">Market</th><th className="p-2">Side</th><th className="p-2">Price</th><th className="p-2">Size</th><th className="p-2">Status</th></tr>
          </thead>
          <tbody>
            {orders.map((o, index) => (
              <tr key={o.order_id || index} className="border-b border-gray-800">
                <td className="p-2">{valueOrUnknown(o.order_id)}</td>
                <td className="p-2">{valueOrUnknown(o.market_ticker || o.market || o.contract_ticker)}</td>
                <td className="p-2">{valueOrUnknown(o.side)}</td>
                <td className="p-2">{valueOrUnknown(o.price_cents)}</td>
                <td className="p-2">{valueOrUnknown(o.size ?? o.quantity)}</td>
                <td className="p-2">{valueOrUnknown(o.status || o.state)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="text-gray-400">No open-order reservations recorded in the durable local risk state.</p>}
    </div>
  );
}
