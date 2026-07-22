import { useEffect, useState } from 'react';
import { fetchJson } from './hooks/useApi';
import { arrayCountOrUnknown, booleanLabel, valueOrUnknown } from './components/TruthValue';

const statusTone = (status) => {
  const value = String(status || '').toUpperCase();
  if (value.includes('VERIFIED') || value.includes('SEALED') || value.includes('CATALOGED')) return 'text-emerald-300';
  if (value.includes('INSUFFICIENT') || value.includes('UNKNOWN') || value.includes('NOT_OBSERVED')) return 'text-amber-300';
  return 'text-sky-300';
};

export default function VNextObservatory() {
  const [snapshot, setSnapshot] = useState(null);
  const [claims, setClaims] = useState(null);
  const [promotion, setPromotion] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      fetchJson('/api/vnext/observatory'),
      fetchJson('/api/vnext/claims'),
      fetchJson('/api/vnext/promotion-review'),
    ])
      .then(([nextSnapshot, nextClaims, nextPromotion]) => {
        setSnapshot(nextSnapshot);
        setClaims(nextClaims);
        setPromotion(nextPromotion);
      })
      .catch((reason) => setError(String(reason.message || reason)));
  }, []);

  return (
    <section className="space-y-6">
      <header className="rounded-xl border border-cyan-800 bg-gray-950 p-5">
        <p className="text-xs uppercase tracking-[0.28em] text-cyan-400">DUMMY vNext</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Intelligence Observatory</h1>
        <p className="mt-2 max-w-4xl text-sm text-gray-300">
          Read-only, evidence-linked projections. This surface cannot submit orders, change authority,
          mutate genomes, or promote candidates.
        </p>
        {snapshot && (
          <div className="mt-4 flex flex-wrap gap-3 text-xs">
            <span className="rounded-full bg-cyan-950 px-3 py-1 text-cyan-200">Authority: {valueOrUnknown(snapshot.authority)}</span>
            <span className="rounded-full bg-gray-800 px-3 py-1 text-gray-200">{valueOrUnknown(snapshot.telemetry_status)}</span>
            <span className="rounded-full bg-gray-800 px-3 py-1 text-gray-200">Snapshot {shortId(snapshot.snapshot_id)}</span>
          </div>
        )}
      </header>

      {error && <div className="rounded-lg border border-red-700 bg-red-950 p-4 text-red-200">{error}</div>}
      {!snapshot && !error && <div className="text-gray-400">Loading evidence projection…</div>}

      {claims && promotion && (
        <div className="grid gap-4 lg:grid-cols-3">
          <article className="rounded-xl border border-amber-800 bg-gray-950 p-5 lg:col-span-2">
            <h2 className="text-lg font-semibold text-white">Claim-by-claim evidence review</h2>
            <p className="mt-2 text-sm text-gray-400">
              Performance supported: {valueOrUnknown(claims.performance_supported_count)}; governance-only: {valueOrUnknown(claims.governance_supported_count)};
              insufficient evidence: {valueOrUnknown(claims.insufficient_evidence_count)}. Material improvement: {booleanLabel(claims.material_improvement_established)}.
            </p>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {!Array.isArray(claims.reviews) && <UnknownCollection label="Claim reviews" />}
              {(Array.isArray(claims.reviews) ? claims.reviews : []).map((review, index) => (
                <div key={review.review_id || index} className="rounded-lg border border-gray-800 bg-gray-900 p-3">
                  <div className="text-sm text-gray-200">{valueOrUnknown(review.definition?.statement)}</div>
                  <div className={`mt-2 text-xs font-semibold ${statusTone(review.verdict)}`}>{valueOrUnknown(review.verdict)}</div>
                  {Array.isArray(review.blockers) && review.blockers.length > 0 && <div className="mt-1 text-[11px] text-amber-400">{review.blockers.length} evidence blocker(s)</div>}
                  {!Array.isArray(review.blockers) && <div className="mt-1 text-[11px] text-amber-400">Evidence blocker count: UNKNOWN</div>}
                </div>
              ))}
            </div>
          </article>
          <article className="rounded-xl border border-rose-800 bg-gray-950 p-5">
            <h2 className="text-lg font-semibold text-white">Promotion review</h2>
            <div className="mt-3 text-sm text-gray-300">{valueOrUnknown(promotion.current_state)} → {valueOrUnknown(promotion.requested_state)}</div>
            <div className="mt-2 text-sm font-semibold text-rose-300">
              {booleanLabel(promotion.transition_eligible, 'ELIGIBLE FOR HUMAN REVIEW', 'BLOCKED')}
            </div>
            <div className="mt-3 text-xs text-gray-400">Human approval required: {booleanLabel(promotion.human_review_required)}</div>
            <div className="mt-1 text-xs text-gray-400">Automatic promotion: {booleanLabel(promotion.automatic_promotion)}</div>
            <div className="mt-1 text-xs text-gray-400">Applied: {booleanLabel(promotion.applied)}</div>
            <div className="mt-3 text-xs text-amber-400">{arrayCountOrUnknown(promotion.blockers)} unresolved evidence blocker(s)</div>
          </article>
        </div>
      )}

      {snapshot && (
        <div className="grid gap-4 lg:grid-cols-2">
          {!Array.isArray(snapshot.panels) && <UnknownCollection label="Observatory panels" />}
          {(Array.isArray(snapshot.panels) ? snapshot.panels : []).map((panel, panelIndex) => (
            <article key={panel.panel || panelIndex} className="rounded-xl border border-gray-700 bg-gray-950 p-5 shadow-lg">
              <h2 className="text-lg font-semibold capitalize text-white">{humanize(panel.panel)}</h2>
              <div className="mt-4 space-y-3">
                {!Array.isArray(panel.claims) && <UnknownCollection label="Panel claims" />}
                {(Array.isArray(panel.claims) ? panel.claims : []).map((claim, claimIndex) => (
                  <div key={claim.claim_id || claimIndex} className="rounded-lg border border-gray-800 bg-gray-900 p-3">
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-sm text-gray-300">{humanize(claim.label)}</span>
                      <span className={`text-xs font-semibold ${statusTone(claim.status)}`}>{valueOrUnknown(claim.status)}</span>
                    </div>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-sm text-white">{JSON.stringify(claim.value, null, 2) ?? 'UNKNOWN'}</pre>
                    <div className="mt-2 text-[11px] text-gray-500">Evidence: {Array.isArray(claim.evidence_ids) ? claim.evidence_ids.join(', ') || 'NONE RECORDED' : 'UNKNOWN'}</div>
                    {Array.isArray(claim.limitations) && claim.limitations.length > 0 && <div className="mt-1 text-[11px] text-amber-400">Limits: {claim.limitations.join('; ')}</div>}
                    {!Array.isArray(claim.limitations) && <div className="mt-1 text-[11px] text-amber-400">Limitations: UNKNOWN</div>}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function shortId(value) {
  return typeof value === 'string' && value ? value.slice(0, 12) : 'UNKNOWN';
}

function humanize(value) {
  return typeof value === 'string' && value ? value.replaceAll('_', ' ') : 'UNKNOWN';
}

function UnknownCollection({ label }) {
  return <div className="rounded border border-amber-800 bg-amber-950/30 p-3 text-sm text-amber-300">{label}: UNKNOWN</div>;
}
