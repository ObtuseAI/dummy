import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function StrategyScan() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/v4/strategies/scan')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Strategy Scan</h1>
      {data ? (
        <div className="bg-gray-800 rounded p-4">
          <p className="text-sm text-gray-400 mb-4">{data.market_ticker} / {data.contract_ticker}</p>
          <div className="space-y-3">
            {(data.scan_results || []).map((r, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{r.family}</div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-2 text-xs text-gray-400">
                  <div>edge: {r.edge_estimate.toFixed(4)}</div>
                  <div>conf: {r.confidence.toFixed(2)}</div>
                  <div>liq: {r.liquidity_score.toFixed(2)}</div>
                  <div>spread: {r.spread_score.toFixed(2)}</div>
                  <div>risk: {r.settlement_risk_score.toFixed(2)}</div>
                </div>
                {r.proposal_summary ? (
                  <div className="mt-2 text-green-400">Proposal: {r.proposal_summary.side} {r.proposal_summary.size} @ {r.proposal_summary.price_cents}¢</div>
                ) : (
                  <div className="mt-2 text-gray-500">No trade: {r.no_trade_reason}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-400">Loading...</p>
      )}
    </div>
  );
}
