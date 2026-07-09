import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function ProposedTrades() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/v3/proposed-trades')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Proposed Trades</h1>

      <div className="grid grid-cols-2 gap-4">
        <Card label="Market" value={data.market_ticker} />
        <Card label="Contract" value={data.contract_ticker} />
        <Card label="Proposals" value={(data.proposals || []).length} />
      </div>

      <Section title={`Proposals (${(data.proposals || []).length})`}>
        {(data.proposals || []).length ? (
          <div className="space-y-3">
            {(data.proposals || []).map((p, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{p.side?.toUpperCase()} {p.quantity} @ {p.price_cents}¢</div>
                <div className="text-gray-400">Strategy: {p.strategy_name || 'unknown'} &middot; Market: {p.market_ticker}</div>
                <div className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                  <KeyValue label="Edge" value={p.edge?.estimate} />
                  <KeyValue label="Confidence" value={p.confidence?.estimate} />
                  <KeyValue label="Liquidity" value={p.liquidity?.estimate} />
                  <KeyValue label="Spread" value={p.spread?.estimate} />
                  <KeyValue label="Settlement Risk" value={p.settlement_risk?.estimate} />
                  <KeyValue label="Cap Impact" value={p.cap_impact?.cents} />
                  <KeyValue label="Compliance" value={p.compliance?.verdict} />
                  <KeyValue label="Proof" value={p.proof_ref} />
                </div>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No proposals</p>}
      </Section>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-4 bg-gray-800 rounded">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xl font-bold">{String(value ?? '-')}</div>
    </div>
  );
}

function KeyValue({ label, value }) {
  return (
    <div className="flex justify-between bg-gray-800 p-2 rounded">
      <span className="text-gray-400">{label}</span>
      <span className="font-mono">{String(value ?? '-')}</span>
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
