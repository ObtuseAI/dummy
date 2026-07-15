import { useEffect, useState } from 'react';

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
    const readJson = (path) => fetch(path).then((response) => {
      if (!response.ok) throw new Error(`${path} unavailable (${response.status})`);
      return response.json();
    });
    Promise.all([
      readJson('/api/vnext/observatory'),
      readJson('/api/vnext/claims'),
      readJson('/api/vnext/promotion-review'),
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
            <span className="rounded-full bg-cyan-950 px-3 py-1 text-cyan-200">Authority: {snapshot.authority}</span>
            <span className="rounded-full bg-gray-800 px-3 py-1 text-gray-200">{snapshot.telemetry_status}</span>
            <span className="rounded-full bg-gray-800 px-3 py-1 text-gray-200">Snapshot {snapshot.snapshot_id.slice(0, 12)}</span>
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
              Performance supported: {claims.performance_supported_count}; governance-only: {claims.governance_supported_count};
              insufficient evidence: {claims.insufficient_evidence_count}. Material improvement: {String(claims.material_improvement_established)}.
            </p>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {claims.reviews.map((review) => (
                <div key={review.review_id} className="rounded-lg border border-gray-800 bg-gray-900 p-3">
                  <div className="text-sm text-gray-200">{review.definition.statement}</div>
                  <div className={`mt-2 text-xs font-semibold ${statusTone(review.verdict)}`}>{review.verdict}</div>
                  {review.blockers.length > 0 && <div className="mt-1 text-[11px] text-amber-400">{review.blockers.length} evidence blocker(s)</div>}
                </div>
              ))}
            </div>
          </article>
          <article className="rounded-xl border border-rose-800 bg-gray-950 p-5">
            <h2 className="text-lg font-semibold text-white">Promotion review</h2>
            <div className="mt-3 text-sm text-gray-300">{promotion.current_state} → {promotion.requested_state}</div>
            <div className="mt-2 text-sm font-semibold text-rose-300">
              {promotion.transition_eligible ? 'Eligible for human review' : 'Blocked'}
            </div>
            <div className="mt-3 text-xs text-gray-400">Human approval required: {String(promotion.human_review_required)}</div>
            <div className="mt-1 text-xs text-gray-400">Automatic promotion: {String(promotion.automatic_promotion)}</div>
            <div className="mt-1 text-xs text-gray-400">Applied: {String(promotion.applied)}</div>
            <div className="mt-3 text-xs text-amber-400">{promotion.blockers.length} unresolved evidence blocker(s)</div>
          </article>
        </div>
      )}

      {snapshot && (
        <div className="grid gap-4 lg:grid-cols-2">
          {snapshot.panels.map((panel) => (
            <article key={panel.panel} className="rounded-xl border border-gray-700 bg-gray-950 p-5 shadow-lg">
              <h2 className="text-lg font-semibold capitalize text-white">{panel.panel.replaceAll('_', ' ')}</h2>
              <div className="mt-4 space-y-3">
                {panel.claims.map((claim) => (
                  <div key={claim.claim_id} className="rounded-lg border border-gray-800 bg-gray-900 p-3">
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-sm text-gray-300">{claim.label.replaceAll('_', ' ')}</span>
                      <span className={`text-xs font-semibold ${statusTone(claim.status)}`}>{claim.status}</span>
                    </div>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-sm text-white">{JSON.stringify(claim.value, null, 2)}</pre>
                    <div className="mt-2 text-[11px] text-gray-500">Evidence: {claim.evidence_ids.join(', ')}</div>
                    {claim.limitations.length > 0 && <div className="mt-1 text-[11px] text-amber-400">Limits: {claim.limitations.join('; ')}</div>}
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
