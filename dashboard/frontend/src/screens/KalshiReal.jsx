import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

const BASE = '/api/read-only/kalshi';

export default function KalshiReal() {
  const [status, setStatus] = useState(null);
  const [account, setAccount] = useState(null);
  const [markets, setMarkets] = useState(null);
  const [positions, setPositions] = useState(null);
  const [orders, setOrders] = useState(null);
  const [fills, setFills] = useState(null);
  const [ticker, setTicker] = useState('');
  const [book, setBook] = useState(null);
  const [errors, setErrors] = useState({});
  const fail = key => error => setErrors(current => ({ ...current, [key]: error.message }));

  useEffect(() => {
    fetchJson(`${BASE}/status`).then(setStatus).catch(fail('status'));
    fetchJson(`${BASE}/account`).then(setAccount).catch(fail('account'));
    fetchJson(`${BASE}/markets`).then(setMarkets).catch(fail('markets'));
    fetchJson(`${BASE}/positions`).then(setPositions).catch(fail('positions'));
    fetchJson(`${BASE}/orders`).then(setOrders).catch(fail('orders'));
    fetchJson(`${BASE}/fills`).then(setFills).catch(fail('fills'));
  }, []);

  function loadBook(rawTicker) {
    const normalized = String(rawTicker || '').trim();
    if (!normalized) {
      setErrors(current => ({ ...current, book: 'Enter an exact contract ticker.' }));
      return;
    }
    setErrors(current => ({ ...current, book: null }));
    setBook(null);
    fetchJson(`${BASE}/orderbook/${encodeURIComponent(normalized)}`).then(setBook).catch(fail('book'));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Kalshi account evidence</h1>
        <p className="mt-1 text-sm text-gray-400">Local risk-state and runtime observations. This page never contacts the broker.</p>
      </div>

      <div className="rounded border-2 border-amber-600 bg-amber-950/50 p-4 text-amber-100">
        <div className="font-black">NOT A CURRENT BROKER ACCOUNT SNAPSHOT</div>
        <p className="mt-1 text-sm">Stored runtime values are labeled unverified. Missing broker data remains UNKNOWN and is never displayed as an empty live account.</p>
      </div>

      {errors.status && <ErrorLine label="Status" error={errors.status} />}
      {status && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card label="Connection verified" value={booleanLabel(status.connection_verified)} />
          <Card label="Connected value (unverified)" value={booleanLabel(status.connected)} />
          <Card label="Runtime flag (unverified)" value={booleanLabel(status.runtime_connected_flag)} />
          <Card label="Connection status" value={status.connection_status} />
          <Card label="Credentials present" value={booleanLabel(status.credentials_present)} />
          <Card label="Mode" value={status.mode} />
          <Card label="Live snapshot" value={booleanLabel(status.live_snapshot_available, 'AVAILABLE', 'NOT AVAILABLE')} />
          <Card label="Source" value={status.source} />
        </div>
      )}

      <PayloadSection title="Stored account state" payload={account} error={errors.account} />
      <CollectionSection title="Current markets" payload={markets} field="markets" error={errors.markets} empty="Verified snapshot contains no markets" />
      <CollectionSection title="Durable local positions" payload={positions} field="positions" error={errors.positions} empty="No positions recorded in the durable local risk state" />
      <CollectionSection title="Durable open-order reservations" payload={orders} field="orders" error={errors.orders} empty="No open-order reservations recorded in the durable local risk state" />
      <CollectionSection title="Current broker fills" payload={fills} field="fills" error={errors.fills} empty="Verified snapshot contains no fills" />

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
        {book && <PayloadTruth payload={book} field="orderbook" />}
      </Section>

      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
        Weather and commodity contracts are data-only. They cannot become prediction or execution targets from this observatory.
      </div>
    </div>
  );
}

function PayloadTruth({ payload, field }) {
  const value = payload?.[field];
  if (value === null || value === undefined) {
    return (
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
        {field} is UNKNOWN. Reason: {valueOrUnknown(payload?.unavailable_reason)} · Source: {valueOrUnknown(payload?.source)}
      </div>
    );
  }
  return (
    <div>
      <EvidenceMeta payload={payload} />
      <pre className="mt-2 max-h-96 overflow-auto rounded bg-gray-900 p-3 text-xs">{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function PayloadSection({ title, payload, error }) {
  return (
    <Section title={title}>
      {error ? <ErrorLine label={title} error={error} /> : !payload ? <p className="text-sm text-gray-400">Loading…</p> : (
        <>
          <EvidenceMeta payload={payload} />
          <pre className="mt-2 max-h-96 overflow-auto rounded bg-gray-900 p-3 text-xs">{JSON.stringify(payload, null, 2)}</pre>
        </>
      )}
    </Section>
  );
}

function CollectionSection({ title, payload, field, error, empty }) {
  const collection = payload?.[field];
  return (
    <Section title={`${title} (${Array.isArray(collection) ? collection.length : 'UNKNOWN'})`}>
      {error ? <ErrorLine label={title} error={error} /> : !payload ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : !Array.isArray(collection) ? (
        <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
          UNKNOWN — {valueOrUnknown(payload.unavailable_reason)} · Source: {valueOrUnknown(payload.source)}
        </div>
      ) : collection.length ? (
        <>
          <EvidenceMeta payload={payload} />
          <pre className="mt-2 max-h-96 overflow-auto rounded bg-gray-900 p-3 text-xs">{JSON.stringify(collection, null, 2)}</pre>
        </>
      ) : (
        <><EvidenceMeta payload={payload} /><p className="mt-2 text-sm text-gray-400">{empty}</p></>
      )}
    </Section>
  );
}

function EvidenceMeta({ payload }) {
  return <div className="text-xs text-gray-400">Source: {valueOrUnknown(payload?.source)} · Status: {valueOrUnknown(payload?.data_status)} · Live snapshot: {booleanLabel(payload?.live_snapshot_available, 'YES', 'NO')}</div>;
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
