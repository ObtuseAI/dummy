import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Forecasts() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/forecasts').then(setData); }, []);
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Forecasts</h1>
      {(data.forecasts || []).map((f, i) => (
        <div key={i} className="bg-gray-800 rounded p-4 text-sm space-y-1">
          <div className="font-semibold">{f.event_title} / {f.contract_title}</div>
          <div className="text-gray-400">Market: {f.market_ticker} | Contract: {f.contract_ticker}</div>
          <div>Market implied prob: {f.market_implied_probability} | Dummy prob: {f.dummy_probability}</div>
          <div>Expected edge: {f.expected_edge} | Edge after fees: {f.edge_after_fees}</div>
          <div>Confidence: {f.confidence_score} | Settlement risk: {f.settlement_risk_score}</div>
          <div className="text-xs text-gray-500">Model: {f.model_summary} | Source: {f.source_summary}</div>
        </div>
      ))}
    </div>
  );
}
