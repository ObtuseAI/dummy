import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v17/mission-state'],
  ['Outcome Ledger', '/api/v17/outcome-ledger'],
  ['Forecast Snapshots', '/api/v17/forecast-snapshots'],
  ['Calibration', '/api/v17/calibration'],
  ['Attribution', '/api/v17/outcome-attribution'],
  ['Bloodline Truth', '/api/v17/bloodline-truth'],
  ['Improvement Proposals', '/api/v17/improvement-proposals'],
  ['Domain Baselines', '/api/v17/domain-baselines'],
  ['Outcome Observer', '/api/v17/outcome-observer'],
];

export default function V17Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const responses = await Promise.all(endpoints.map(([, path]) => fetchJson(path)));
        setData(Object.fromEntries(endpoints.map(([title], index) => [title, responses[index]])));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const summary = useMemo(() => {
    const mission = data['Mission State']?.mission_state || {};
    const ledger = data['Outcome Ledger']?.outcome_ledger || {};
    const calibration = data.Calibration?.calibration || {};
    const attribution = data.Attribution?.outcome_attribution || {};
    const observer = data['Outcome Observer']?.outcome_observer || {};
    return [
      ['Mission', mission.mission_state_verdict || 'UNKNOWN'],
      ['Ledger', ledger.verdict || 'UNKNOWN'],
      ['Records', ledger.record_count ?? '0'],
      ['Sample', calibration.sample_quality || 'UNKNOWN'],
      ['Brier', calibration.brier_score ?? 'NA'],
      ['Attribution', attribution.causality_claim || 'UNKNOWN'],
      ['Observer', observer.mode || 'UNKNOWN'],
      ['Fabricated', observer.fabricated_outcome ? 'CHECK' : 'NO'],
      ['Submit', mission.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'CHECK'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V17 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V17 Outcome Truth Loop</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {summary.map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
            <div className="mt-1 text-base font-semibold text-white break-words">{String(value)}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {endpoints.map(([title]) => (
          <Section key={title} title={title} data={data[title]} />
        ))}
      </div>
    </div>
  );
}

function Section({ title, data }) {
  return (
    <div className="bg-gray-800 rounded p-4 border border-gray-700">
      <h2 className="text-base font-semibold mb-2">{title}</h2>
      <pre className="text-xs overflow-auto max-h-80 bg-gray-900 p-2 rounded">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

