import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import ForecastQuality from '../components/ForecastQuality';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function StrategyCandidates() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetchJson('/strategies')
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;
  const registered = Array.isArray(data.registered_strategies) ? data.registered_strategies : null;
  const rawCandidates = Array.isArray(data.repo_derived_candidates) ? data.repo_derived_candidates : null;
  const candidates = rawCandidates === null ? null : rawCandidates.filter(candidate => !isDataOnlyCandidate(candidate));
  const locallyExcluded = rawCandidates === null ? null : rawCandidates.length - candidates.length;
  const excludedCount = data.data_only_candidates_excluded ?? locallyExcluded;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Strategy Candidates</h1>

      <Section title={`Registered Dummy Strategies (${registered === null ? 'UNKNOWN' : registered.length})`}>
        {registered === null ? <Unknown label="registered strategy" /> : registered.length ? <div className="flex flex-wrap gap-2">
          {registered.map(name => (
            <span key={name} className="px-2 py-1 bg-blue-900 rounded text-sm">{name}</span>
          ))}
        </div> : <p className="text-sm text-gray-400">No registered strategies reported by the source.</p>}
      </Section>

      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
        Candidate metadata is stored research intake. A listed candidate has no forecasting or execution authority unless separate settlement-backed promotion evidence exists.
      </div>
      <div className="rounded border border-emerald-800 bg-emerald-950/30 p-3 text-sm text-emerald-200">
        Weather and commodity candidates are data-only and excluded from this prediction inventory. Excluded: {valueOrUnknown(excludedCount)}.
      </div>

      <Section title={`Repo-Derived Candidates (${candidates === null ? 'UNKNOWN' : candidates.length})`}>
        {candidates === null ? <Unknown label="candidate" /> : candidates.length ? (
          <div className="space-y-3 max-h-[32rem] overflow-y-auto">
            {candidates.map((c, i) => (
              <div key={i} className="bg-gray-900 p-3 rounded text-sm">
                <div className="font-semibold">{valueOrUnknown(c.strategy_name)}</div>
                <div className="text-gray-400">Source: {valueOrUnknown(c.repo)} ({valueOrUnknown(c.source_category)})</div>
                <div className="mt-1">{valueOrUnknown(c.description)}</div>
                <div className="mt-1 text-xs text-gray-400">Output: {valueOrUnknown(c.output)} &middot; live_order_endpoints: {booleanLabel(c.calls_live_order_endpoints)}</div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded bg-gray-800 px-2 py-1">Validation: {valueOrUnknown(c.validation_status)}</span>
                  <span className="rounded bg-gray-800 px-2 py-1">Sample: {valueOrUnknown(c.sample_size)}</span>
                  {c.thin_data === true && <span className="rounded bg-amber-900 px-2 py-1 text-amber-200">THIN DATA</span>}
                  {c.thin_data == null && <span className="rounded bg-gray-800 px-2 py-1">Thin-data status: UNKNOWN</span>}
                </div>
                <ForecastQuality quality={c.forecast_quality} />
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-gray-400">No candidates</p>}
      </Section>
    </div>
  );
}

function Unknown({ label }) {
  return <p className="text-sm font-semibold text-amber-300">UNKNOWN — {label} collection unavailable.</p>;
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
