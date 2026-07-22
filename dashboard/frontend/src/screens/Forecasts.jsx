import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { valueOrUnknown } from '../components/TruthValue';

// Defence in depth for legacy snapshots. The backend applies the canonical
// target policy, but a copied/stale artifact must not restore weather or
// commodity contracts to the prediction screen.
const DATA_ONLY_TICKER_PREFIXES = [
  'WEATHER', 'KXHIGH', 'KXLOW', 'KXRAIN', 'KXSNOW',
  'COMMODITY', 'KXOIL', 'KXWTI', 'KXNATGAS', 'KXNGAS',
  'KXGAS', 'KXGOLD',
];

export default function Forecasts() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/forecasts').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Forecasts unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;
  const forecasts = Array.isArray(data.forecasts)
    ? data.forecasts.filter(forecast => !isDataOnlyForecast(forecast))
    : null;
  const dataOnlyExcluded = data.data_only_forecasts_excluded;
  const settlementClaim = data.settlement_backed_performance_claim;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Stored Forecast Observations</h1>
      <div className="rounded border-2 border-amber-500 bg-amber-950/60 p-4 text-amber-100">
        <div className="text-lg font-black uppercase">{valueOrUnknown(data.data_status)}</div>
        <div className="mt-1 font-bold">
          {settlementClaim === false
            ? 'NO SETTLEMENT-BACKED PERFORMANCE CLAIM'
            : settlementClaim === true
              ? 'Settlement-backed claim flag present — inspect the underlying evidence before relying on it'
              : 'SETTLEMENT-BACKED CLAIM STATUS UNKNOWN'}
        </div>
        <p className="mt-2 text-sm text-amber-200">
          These are stored forecast observations, not a live feed, verified edge, recommendation, or authorization to trade.
        </p>
        <div className="mt-2 text-xs text-amber-300">
          Source: {valueOrUnknown(data.source)} · Eligible rows: {valueOrUnknown(data.count)} · Valid stored rows scanned: {valueOrUnknown(data.stored_record_count)} · Malformed skipped: {valueOrUnknown(data.skipped_malformed)}
        </div>
        <div className="mt-1 text-xs text-amber-300">
          Fresh stored: {valueOrUnknown(data.freshness_counts?.fresh_stored)} · Stale: {valueOrUnknown(data.freshness_counts?.stale_stored)} · Missing/invalid time: {valueOrUnknown((data.freshness_counts?.timestamp_missing ?? 0) + (data.freshness_counts?.timestamp_invalid ?? 0))}
        </div>
      </div>
      <div className="rounded border border-emerald-800 bg-emerald-950/30 p-3 text-sm text-emerald-200">
        Weather and commodity targets are excluded from forecasting; those feeds are data-only. Stored target forecasts excluded: {valueOrUnknown(dataOnlyExcluded)}.
      </div>
      {forecasts === null && <p className="text-amber-300">Forecast collection status: UNKNOWN</p>}
      {forecasts?.length === 0 && <p className="text-gray-400">No stored forecast observations</p>}
      {(forecasts || []).map((f, i) => (
        <div key={i} className={`rounded border p-4 text-sm space-y-1 ${f.freshness_status === 'fresh_stored' ? 'border-gray-700 bg-gray-800' : 'border-amber-700 bg-amber-950/30'}`}>
          <div className="font-semibold">{valueOrUnknown(f.event_title)} / {valueOrUnknown(f.contract_title)}</div>
          <div className="text-gray-400">Market: {valueOrUnknown(f.market_ticker)} | Contract: {valueOrUnknown(f.contract_ticker)}</div>
          <div className="font-bold uppercase text-amber-300">
            {valueOrUnknown(f.freshness_status)} · {formatAge(f.observation_age_seconds)} · Mode: {valueOrUnknown(f.model_mode ?? f.source_mode)}
          </div>
          <div>Market implied probability: {valueOrUnknown(f.market_implied_probability)} | Dummy probability: {valueOrUnknown(f.dummy_probability)}</div>
          <div>Expected edge: {valueOrUnknown(f.expected_edge)} | Edge after fees: {valueOrUnknown(f.edge_after_fees)}</div>
          <div>Confidence: {valueOrUnknown(f.confidence_score)} | Settlement risk: {valueOrUnknown(f.settlement_risk_score)}</div>
          <div className="text-xs text-gray-500">Model: {valueOrUnknown(f.model_summary)} | Source: {valueOrUnknown(f.source_summary)}</div>
          <div className="text-xs font-semibold uppercase text-amber-300">
            Actionability: {f.row_actionable === false ? 'NON-ACTIONABLE' : 'UNKNOWN'} · {valueOrUnknown(f.actionability_reason)}
          </div>
        </div>
      ))}
    </div>
  );
}

function isDataOnlyForecast(forecast) {
  const ticker = String(
    forecast?.contract_ticker ?? forecast?.market_ticker ?? '',
  ).trim().toUpperCase();
  const category = String(
    forecast?.vertical ?? forecast?.category ?? '',
  ).trim().toLowerCase();
  return ['weather', 'commodity', 'commodities'].includes(category)
    || DATA_ONLY_TICKER_PREFIXES.some(prefix => ticker.startsWith(prefix));
}

function formatAge(seconds) {
  if (seconds === null || seconds === undefined || seconds === '') return 'AGE UNKNOWN';
  if (!Number.isFinite(Number(seconds))) return 'AGE UNKNOWN';
  const hours = Math.max(0, Number(seconds)) / 3600;
  if (hours < 1) return `${Math.round(hours * 60)}m old`;
  if (hours < 48) return `${hours.toFixed(1)}h old`;
  return `${(hours / 24).toFixed(1)}d old`;
}
