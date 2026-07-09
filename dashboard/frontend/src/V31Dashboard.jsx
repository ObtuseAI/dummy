import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v31/mission-state'],
  ['Gate', '/api/v31/gate'],
  ['Probe Runner', '/api/v31/probe-runner'],
  ['Evidence', '/api/v31/evidence'],
  ['Probes', '/api/v31/probes'],
  ['Closure', '/api/v31/closure'],
  ['Scoring', '/api/v31/scoring'],
  ['Cache Audit', '/api/v31/cache-audit'],
  ['Source Truth', '/api/v31/source-truth'],
  ['Safety', '/api/v31/safety'],
];

export default function V31Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v17 || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Gate', mission.public_probe_gate_state || 'UNKNOWN'],
      ['Probe Runs', mission.probe_run_count ?? '0'],
      ['Families', mission.probe_source_family_count ?? '0'],
      ['Evidence', mission.live_public_evidence_packet_count ?? '0'],
      ['Normalized', mission.normalized_live_public_evidence_count ?? '0'],
      ['Due', mission.due_forecast_count ?? '0'],
      ['Observed', mission.observed_forecast_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Calibration', mission.live_calibration_seed_status || 'UNKNOWN'],
      ['Sports', mission.sports_source_mode || 'UNKNOWN'],
      ['Safety', mission.no_public_probe_gate_to_execution_bridge_status || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V31 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V31 Readonly Public Probes</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
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
