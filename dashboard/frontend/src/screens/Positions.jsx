import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Positions() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/positions').then(setData); }, []);
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Positions</h1>
      {(data.positions || []).length ? (
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-800">
            <tr><th className="p-2">Market</th><th className="p-2">Contract</th><th className="p-2">Side</th><th className="p-2">Quantity</th><th className="p-2">Avg Price</th><th className="p-2">PnL</th></tr>
          </thead>
          <tbody>
            {data.positions.map(p => (
              <tr key={p.market_ticker} className="border-b border-gray-800">
                <td className="p-2">{p.market_ticker}</td>
                <td className="p-2">{p.contract_ticker}</td>
                <td className="p-2">{p.side}</td>
                <td className="p-2">{p.quantity}</td>
                <td className="p-2">{p.avg_price_cents}</td>
                <td className="p-2">{p.unrealized_pnl_cents}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="text-gray-400">No positions</p>}
    </div>
  );
}
