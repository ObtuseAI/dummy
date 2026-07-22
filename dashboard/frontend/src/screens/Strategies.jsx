import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function Strategies() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/strategies').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Strategy evidence unavailable: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;
  const registered = Array.isArray(data.registered_strategies) ? data.registered_strategies : null;
  const rawCandidates = Array.isArray(data.repo_derived_candidates) ? data.repo_derived_candidates : null;
  const candidates = rawCandidates === null ? null : rawCandidates.filter(candidate => !isDataOnlyCandidate(candidate));
  const locallyExcluded = rawCandidates === null ? null : rawCandidates.length - candidates.length;
  const excludedCount = data.data_only_candidates_excluded ?? locallyExcluded;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Strategies</h1>
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-100">
        Stored research inventory only. Registration or extraction is not validation, forecast authority, promotion, or permission to execute. Source: {valueOrUnknown(data.source)} · Status: {valueOrUnknown(data.data_status)}
      </div>
      <div className="rounded border border-emerald-800 bg-emerald-950/30 p-3 text-sm text-emerald-200">
        Weather and commodity strategy candidates are excluded from prediction and execution. Data-only candidates excluded: {valueOrUnknown(excludedCount)}.
      </div>

      <Section title={`Registered Dummy Strategies (${registered === null ? 'UNKNOWN' : registered.length})`}>
        {registered === null ? <Unknown /> : registered.length ? <div className="flex flex-wrap gap-2">
          {registered.map(name => (
            <span key={name} className="px-2 py-1 bg-blue-900 rounded text-sm">{name}</span>
          ))}
        </div> : <p className="text-sm text-gray-400">No registered strategies reported by the source.</p>}
      </Section>

      <Section title={`Repo-Derived Candidates (${candidates === null ? 'UNKNOWN' : candidates.length})`}>
        {candidates === null ? <Unknown /> : candidates.length ? <div className="space-y-3">
          {candidates.map((c, i) => (
            <div key={i} className="bg-gray-900 p-3 rounded text-sm">
              <div className="font-semibold">{valueOrUnknown(c.strategy_name)}</div>
              <div className="text-gray-400">Source: {valueOrUnknown(c.repo)} ({valueOrUnknown(c.source_category)})</div>
              <div className="mt-1">{valueOrUnknown(c.description)}</div>
              <div className="mt-1 text-xs text-amber-300">Output: {valueOrUnknown(c.output)} | live_order_endpoints: {booleanLabel(c.calls_live_order_endpoints)}</div>
            </div>
          ))}
        </div> : <p className="text-sm text-gray-400">No repo-derived candidates recorded in the verified source.</p>}
      </Section>
    </div>
  );
}

function Unknown() {
  return <p className="text-sm font-semibold text-amber-300">UNKNOWN — source collection unavailable.</p>;
}

function isDataOnlyCandidate(candidate) {
  const marketTypes = Array.isArray(candidate?.market_types)
    ? candidate.market_types.map(value => String(value).toLowerCase())
    : [];
  const strategyName = String(candidate?.strategy_name || '').toLowerCase();
  const exactDataOnlyStrategy = ['kalshiweatherforecaststrategy', 'commoditiesenergystrategy']
    .includes(strategyName.replace(/[^a-z]/g, ''));
  return marketTypes.some(value => ['weather', 'commodity', 'commodities', 'energy'].includes(value))
    || marketTypes.some(value => ['stock', 'stocks', 'equity', 'equities', 'index', 'indices'].includes(value))
    || strategyName.replace(/[^a-z]/g, '') === 'stockmacromomentumstrategy'
    || exactDataOnlyStrategy
    || (marketTypes.length === 0 && (strategyName.includes('weather') || strategyName.includes('commodit')));
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
    </div>
  );
}
