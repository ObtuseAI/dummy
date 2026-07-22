import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function Kalshi() {
  const [status, setStatus] = useState(null);
  const [markets, setMarkets] = useState(null);
  const [ticker, setTicker] = useState('');
  const [book, setBook] = useState(null);
  const [errors, setErrors] = useState({});
  const fail = key => error => setErrors(current => ({ ...current, [key]: error.message }));

  useEffect(() => {
    fetchJson('/api/read-only/kalshi/status').then(setStatus).catch(fail('status'));
    fetchJson('/api/read-only/kalshi/markets').then(setMarkets).catch(fail('markets'));
  }, []);

  function loadBook(rawTicker) {
    const normalized = String(rawTicker || '').trim();
    if (!normalized) {
      setErrors(current => ({ ...current, book: 'Enter a contract ticker.' }));
      return;
    }
    setErrors(current => ({ ...current, book: null }));
    setBook(null);
    fetchJson(`/api/read-only/kalshi/orderbook/${encodeURIComponent(normalized)}`)
      .then(setBook)
      .catch(fail('book'));
  }

  const events = Array.isArray(markets?.events) ? markets.events : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Kalshi market observatory</h1>
        <p className="mt-1 text-sm text-gray-400">Local, read-only evidence surface. Opening this page never contacts the broker.</p>
      </div>

      <div className="rounded border-2 border-cyan-600 bg-cyan-950/50 p-4 text-cyan-100">
        <div className="font-black">READ-ONLY LOCAL OBSERVATIONS</div>
        <p className="mt-1 text-sm">No live market list or order book is invented when a current local snapshot is unavailable.</p>
      </div>
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
        Weather and commodity contracts are data-only. They are never prediction, ranking, paper-trade, or execution targets.
      </div>

      {errors.status && <ErrorLine label="Runtime status" error={errors.status} />}
      {status && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card label="Connection verified" value={booleanLabel(status.connection_verified)} />
          <Card label="Connected value (unverified)" value={booleanLabel(status.connected)} />
          <Card label="Runtime flag (unverified)" value={booleanLabel(status.runtime_connected_flag)} />
          <Card label="Connection status" value={status.connection_status} />
          <Card label="Mode" value={status.mode} />
          <Card label="Credentials present" value={booleanLabel(status.credentials_present)} />
          <Card label="Stored balance (unverified)" value={status.balance_cents} />
          <Card label="Balance evidence" value={status.balance_status} />
          <Card label="Live snapshot" value={booleanLabel(status.live_snapshot_available, 'AVAILABLE', 'NOT AVAILABLE')} />
          <Card label="Source" value={status.source} />
        </div>
      )}

      <Section title="Current market snapshot">
        {errors.markets ? <ErrorLine label="Markets" error={errors.markets} /> : !markets ? (
          <p className="text-sm text-gray-400">Loading local snapshot status…</p>
        ) : events === null ? (
          <Unavailable payload={markets} noun="market snapshot" />
        ) : events.length === 0 ? (
          <p className="text-sm text-gray-400">The verified local snapshot contains no events.</p>
        ) : (
          <div className="max-h-96 space-y-3 overflow-y-auto">
            {events.map((event, index) => (
              <div key={event.event_ticker || event.ticker || index} className="rounded bg-gray-900 p-3 text-sm">
                <div className="font-semibold">{valueOrUnknown(event.event_ticker || event.ticker)}</div>
                <div className="text-gray-400">{valueOrUnknown(event.title)}</div>
                <MarketButtons markets={event.markets} onSelect={marketTicker => {
                  setTicker(marketTicker);
                  loadBook(marketTicker);
                }} />
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Local order-book lookup">
        <div className="mb-3 flex gap-2">
          <input
            type="text"
            value={ticker}
            onChange={event => setTicker(event.target.value)}
            onKeyDown={event => event.key === 'Enter' && loadBook(ticker)}
            className="flex-1 rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm"
            placeholder="Enter an exact Kalshi contract ticker"
          />
          <button
            type="button"
            disabled={!ticker.trim()}
            onClick={() => loadBook(ticker)}
            className="rounded bg-blue-700 px-3 py-2 text-sm hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Check local snapshot
          </button>
        </div>
        {errors.book && <ErrorLine label="Order book" error={errors.book} />}
        {!book && !errors.book && <p className="text-sm text-gray-400">No ticker selected. Nothing is loaded automatically.</p>}
        {book?.orderbook === null && <Unavailable payload={book} noun="order-book snapshot" />}
        {book?.orderbook && (
          <div className="rounded bg-gray-900 p-3 text-sm">
            <div className="mb-2">Ticker: {valueOrUnknown(book.orderbook.market_ticker || book.orderbook.contract_ticker || ticker)}</div>
            <TargetPolicy policy={book.target_policy} />
            <div className="mt-3 grid grid-cols-2 gap-4">
              <BookSide title="Bids" tone="text-green-400" levels={book.orderbook.bids} />
              <BookSide title="Asks" tone="text-red-400" levels={book.orderbook.asks} />
            </div>
            <div className="mt-2 text-xs text-gray-400">Source: {valueOrUnknown(book.source)} · Status: {valueOrUnknown(book.data_status)}</div>
          </div>
        )}
      </Section>
    </div>
  );
}

function MarketButtons({ markets, onSelect }) {
  if (!Array.isArray(markets)) {
    return <div className="mt-2 text-xs font-semibold text-amber-300">Event market collection: UNKNOWN</div>;
  }
  if (markets.length === 0) {
    return <div className="mt-2 text-xs text-gray-400">Verified event snapshot contains no markets.</div>;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {markets.map((market, index) => (
        <button
          type="button"
          key={market.ticker || index}
          disabled={!market.ticker}
          onClick={() => onSelect(market.ticker)}
          className="rounded bg-gray-800 px-2 py-1 text-left text-xs hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span>{valueOrUnknown(market.ticker)}: {valueOrUnknown(market.title)}</span>
          <TargetPolicy policy={market.target_policy} />
        </button>
      ))}
    </div>
  );
}

function TargetPolicy({ policy }) {
  if (!policy) return <span className="ml-2 rounded bg-gray-700 px-2 py-0.5 text-[10px] font-bold">ELIGIBILITY UNKNOWN</span>;
  if (policy.role === 'data_only') return <span className="ml-2 rounded bg-amber-900 px-2 py-0.5 text-[10px] font-bold text-amber-200">DATA ONLY · NO PREDICTION/EXECUTION</span>;
  return <span className="ml-2 rounded bg-gray-700 px-2 py-0.5 text-[10px] font-bold">ELIGIBILITY UNVERIFIED</span>;
}

function BookSide({ title, tone, levels }) {
  if (!Array.isArray(levels)) return <div><div className={`${tone} mb-1 font-semibold`}>{title}</div><div>UNKNOWN</div></div>;
  return (
    <div>
      <div className={`${tone} mb-1 font-semibold`}>{title}</div>
      {levels.length ? levels.map((level, index) => <div key={index}>{valueOrUnknown(level.price)} × {valueOrUnknown(level.size)}</div>) : <div className="text-gray-400">No levels</div>}
    </div>
  );
}

function Unavailable({ payload, noun }) {
  return (
    <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
      Current {noun} unavailable. Reason: {valueOrUnknown(payload?.unavailable_reason)}. This is UNKNOWN, not zero or empty.
    </div>
  );
}

function ErrorLine({ label, error }) {
  return <p className="text-sm text-red-400">{label} unavailable: {error}</p>;
}

function Card({ label, value }) {
  return (
    <div className="rounded bg-gray-800 p-4">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="break-words text-xl font-bold">{String(valueOrUnknown(value))}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="rounded bg-gray-800 p-4">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </div>
  );
}
