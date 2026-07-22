import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function Proof() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchJson('/proof').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;
  if (!data) return <div>Loading...</div>;
  const proofs = Array.isArray(data.proofs) ? data.proofs : null;
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Proof Ledger</h1>
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-100">
        Integrity validation does not grant forecasting, profitability, promotion, or execution authority. Authority granted: {booleanLabel(data.proof_authority_granted)} · Status: {valueOrUnknown(data.data_status)}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card label="Proof Records" value={data.proof_count} />
        <Card label="Shown" value={proofs === null ? null : proofs.length} />
        <Card label="Invalid" value={data.invalid_count} />
        <Card label="Source" value={data.source} />
      </div>
      <div className="space-y-2">
        {(proofs || []).map((proof, index) => (
          <div key={proof.ref_id || index} className="rounded bg-gray-800 p-3 text-sm">
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-semibold">{proof.component || 'unknown component'}</span>
              <span className={proof.verdict === 'PASS' ? 'text-green-400' : proof.verdict ? 'text-amber-300' : 'text-gray-400'}>{proof.verdict || 'UNKNOWN'}</span>
            </div>
            <div className="mt-1 text-xs text-gray-400">{proof.timestamp || 'timestamp unknown'} · {proof.ref_id || 'reference unknown'}</div>
            {proof.payload_hash && <div className="mt-1 truncate font-mono text-xs text-gray-500">{proof.payload_hash}</div>}
          </div>
        ))}
        {proofs === null && <p className="text-sm font-semibold text-amber-300">Proof collection status: UNKNOWN.</p>}
        {proofs?.length === 0 && <p className="text-sm text-gray-400">No integrity-valid proof records are present in this bounded view.</p>}
      </div>
    </div>
  );
}

function Card({ label, value }) {
  return <div className="rounded bg-gray-800 p-3"><div className="text-xs text-gray-400">{label}</div><div className="text-lg font-bold">{String(value ?? 'UNKNOWN')}</div></div>;
}
