import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function KalshiReal() {
  const [status, setStatus] = useState(null);
  const [account, setAccount] = useState(null);
  const [markets, setMarkets] = useState(null);
  const [positions, setPositions] = useState(null);
  const [orders, setOrders] = useState(null);
  const [fills, setFills] = useState(null);
  const [ticker, setTicker] = useState('WEATHER-NYC-RAIN-YES');
  const [book, setBook] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/v4/kalshi/status').then(setStatus).catch(e => setError(e.message));
    fetchJson('/v4/kalshi/account').then(setAccount).catch(e => setError(e.message));
    fetchJson('/v4/kalshi/markets').then(setMarkets).catch(e => setError(e.message));
    fetchJson('/v4/kalshi/positions').then(setPositions).catch(e => setError(e.message));
    fetchJson('/v4/kalshi/orders').then(setOrders).catch(e => setError(e.message));
    fetchJson('/v4/kalshi/fills').then(setFills).catch(e => setError(e.message));
    loadBook(ticker);
  }, []);

  function loadBook(t) {
    fetchJson(`/v4/kalshi/orderbook/${encodeURIComponent(t)}`)
      .then(setBook)
      .catch(e => setError(e.message));
  }

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Real Kalshi</h1>

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Connected" value={status.connected ? 'Yes' : 'No'} />
          <Card label="Credentials Present" value={status.credentials_present ? 'Yes' : 'No'} />
          <Card label="Mode" value={status.mode} />
          <Card label="Source" value={account?.source || 'live'} />
        </div>
      )}

      <Section title="Account">
        {account ? <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto">{JSON.stringify(account, null, 2)}</pre> : <p className="text-sm text-gray-400">No account data</p>}
      </Section>

      <Section title={`Markets (${(markets?.markets || markets?.events || []).length} items)`}>
        {markets ? <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto max-h-96">{JSON.stringify(markets, null, 2)}</pre> : <p className="text-sm text-gray-400">No markets</p>}
      </Section>

      <Section title="Positions">
        {positions ? <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto max-h-96">{JSON.stringify(positions, null, 2)}</pre> : <p className="text-sm text-gray-400">No positions</p>}
      </Section>

      <Section title="Resting Orders">
        {orders ? <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto max-h-96">{JSON.stringify(orders, null, 2)}</pre> : <p className="text-sm text-gray-400">No resting orders</p>}
      </Section>

      <Section title="Fills">
        {fills ? <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto max-h-96">{JSON.stringify(fills, null, 2)}</pre> : <p className="text-sm text-gray-400">No fills</p>}
      </Section>

      <Section title="Orderbook Lookup">
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={ticker}
            onChange={e => setTicker(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1 text-sm flex-1"
            placeholder="Ticker"
          />
          <button onClick={() => loadBook(ticker)} className="px-3 py-1 bg-blue-700 rounded text-sm hover:bg-blue-600">Load</button>
        </div>
        {book ? <pre className="bg-gray-900 p-3 rounded text-xs overflow-x-auto">{JSON.stringify(book, null, 2)}</pre> : <p className="text-sm text-gray-400">Loading...</p>}
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
