import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Live Liquidity Proof', '/api/v11/liquidity-proof'],
  ['Orderbook Liquidity Model', '/api/v11/orderbook-liquidity'],
  ['Fill Quality Estimate', '/api/v11/fill-quality'],
  ['Shadow Order Packets', '/api/v11/shadow-orders'],
  ['Micro-Order Arming', '/api/v11/micro-order-arming'],
  ['Cancel/Reconcile Rehearsal', '/api/v11/cancel-reconcile'],
  ['Order Lifecycle', '/api/v11/order-lifecycle'],
  ['Liquidity Aggression Governor', '/api/v11/liquidity-aggression'],
  ['Post-Trade Ledger Skeleton', '/api/v11/post-trade-ledger'],
];

export default function V11Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const responses = await Promise.all(endpoints.map(([, path]) => fetchJson(path)));
        setData(Object.fromEntries(endpoints.map(([title], index) => [title, responses[index]])));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const summary = useMemo(() => {
    const liquidity = data['Live Liquidity Proof'] || {};
    const arming = data['Micro-Order Arming'] || {};
    const aggression = data['Liquidity Aggression Governor'] || {};
    const orderbook = data['Orderbook Liquidity Model'] || {};
    return [
      ['Liquidity', liquidity.verdict || 'UNKNOWN'],
      ['Submit', liquidity.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Firewall', liquidity.firewall_rehearsal_status || 'UNKNOWN'],
      ['Arming', arming.readiness?.readiness?.verdict || 'UNKNOWN'],
      ['Aggression', aggression.decision?.decision || 'UNKNOWN'],
      ['Orderbook', orderbook.analysis?.execution_feasibility_score?.status || 'UNKNOWN'],
      ['Sample Book', orderbook.sample_orderbook_used ? 'YES' : 'NO'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V11 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V11 Dashboard</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {summary.map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
            <div className="mt-1 text-lg font-semibold text-white break-words">{String(value)}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {endpoints.map(([title]) => (
          <Section key={title} title={title} data={data[title]} />
        ))}
      </div>
    </div>
  );
}

function Section({ title, data }) {
  return (
    <div className="bg-gray-800 rounded p-4 border border-gray-700">
      <h2 className="text-base font-semibold mb-2">{title}</h2>
      <pre className="text-xs overflow-auto max-h-80 bg-gray-900 p-2 rounded">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
