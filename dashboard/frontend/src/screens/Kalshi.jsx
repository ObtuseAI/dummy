import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Kalshi() {
  const [status, setStatus] = useState(null);
  const [markets, setMarkets] = useState(null);
  const [ticker, setTicker] = useState('WEATHER-NYC-RAIN-YES');
  const [book, setBook] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/v3/kalshi/status')
      .then(setStatus)
      .catch(e => setError(e.message));
    fetchJson('/v3/kalshi/markets')
      .then(setMarkets)
      .catch(e => setError(e.message));
    loadBook('WEATHER-NYC-RAIN-YES');
  }, []);

  function loadBook(t) {
    fetchJson(`/v3/kalshi/orderbook/${encodeURIComponent(t)}`)
      .then(setBook)
      .catch(e => setError(e.message));
  }

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Kalshi Live</h1>

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Connected" value={status.connected ? 'Yes' : 'No'} />
          <Card label="Mode" value={status.mode} />
          <Card label="Balance (¢)" value={status.balance_cents} />
          <Card label="API Key Present" value={status.api_key_id_present ? 'Yes' : 'No'} />
          <Card label="Positions" value={(status.positions || []).length} />
          <Card label="Resting Orders" value={(status.resting_orders || []).length} />
          <Card label="Fills" value={(status.fills || []).length} />
          <Card label="Source" value={status.source} />
        </div>
      )}

      <Section title="Positions">
        {(status?.positions || []).length ? (
          <JsonList items={status.positions} />
        ) : <p className="text-sm text-gray-400">No positions</p>}
      </Section>

      <Section title="Resting Orders">
        {(status?.resting_orders || []).length ? (
          <JsonList items={status.resting_orders} />
        ) : <p className="text-sm text-gray-400">No resting orders</p>}
      </Section>

      <Section title="Fills">
        {(status?.fills || []).length ? (
          <JsonList items={status.fills} />
        ) : <p className="text-sm text-gray-400">No fills</p>}
      </Section>

      <Section title={`Markets (${(markets?.events || []).length} events)`}>
        {(markets?.events || []).length ? (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {(markets.events || []).map((ev, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{ev.event_ticker}</div>
                <div className="text-gray-400">{ev.title}</div>
                <div className="mt-1 flex flex-wrap gap-2">
                  {(ev.markets || []).map(m => (
                    <span key={m.ticker} className="px-2 py-1 bg-gray-800 rounded text-xs">{m.ticker}: {m.title}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No markets</p>}
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
          <button
            onClick={() => loadBook(ticker)}
            className="px-3 py-1 bg-blue-700 rounded text-sm hover:bg-blue-600"
          >
            Load
          </button>
        </div>
        {book ? (
          <div className="bg-gray-900 p-3 rounded text-sm font-mospace">
            <div className="mb-2">Ticker: {book.orderbook?.market_ticker || book.orderbook?.contract_ticker || ticker}</div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-green-400 font-semibold mb-1">Bids</div>
                {(book.orderbook?.bids || []).map((b, i) => (
                  <div key={i}>{b.price} &times; {b.size}</div>
                ))}
              </div>
              <div>
                <div className="text-red-400 font-semibold mb-1">Asks</div>
                {(book.orderbook?.asks || []).map((a, i) => (
                  <div key={i}>{a.price} &times; {a.size}</div>
                ))}
              </div>
            </div>
            <div className="mt-2 text-gray-400 text-xs">Source: {book.source}</div>
          </div>
        ) : <p className="text-sm text-gray-400">Loading...</p>}
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
