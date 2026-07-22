import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { valueOrUnknown } from '../components/TruthValue';

export default function Positions() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/api/read-only/kalshi/positions').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Positions unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;
  const positions = Array.isArray(data.positions) ? data.positions : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Positions</h1>
      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Durable local fill/exposure evidence only — not a current broker account snapshot. Source: {valueOrUnknown(data.source)} · Status: {valueOrUnknown(data.data_status)}
      </div>
      {positions === null ? (
        <p className="font-semibold text-amber-300">Position collection status: UNKNOWN — durable exposure state unavailable.</p>
      ) : positions.length ? (
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-800">
            <tr><th className="p-2">Market</th><th className="p-2">Contract</th><th className="p-2">Side</th><th className="p-2">Quantity</th><th className="p-2">Avg Price</th><th className="p-2">PnL</th></tr>
          </thead>
          <tbody>
            {positions.map((p, index) => (
              <tr key={`${p.market_ticker || 'unknown'}-${p.contract_ticker || index}-${p.side || index}`} className="border-b border-gray-800">
                <td className="p-2">{valueOrUnknown(p.market_ticker)}</td>
                <td className="p-2">{valueOrUnknown(p.contract_ticker)}</td>
                <td className="p-2">{valueOrUnknown(p.side)}</td>
                <td className="p-2">{valueOrUnknown(p.quantity)}</td>
                <td className="p-2">{valueOrUnknown(p.avg_price_cents)}</td>
                <td className="p-2">{valueOrUnknown(p.unrealized_pnl_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="text-gray-400">No positions recorded in the durable local risk state.</p>}
    </div>
  );
}
