import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v30/mission-state'],
  ['Adapters', '/api/v30/adapters'],
  ['Fixtures', '/api/v30/fixtures'],
  ['Normalization', '/api/v30/normalization'],
  ['Settlement', '/api/v30/settlement'],
  ['Closure Dry Run', '/api/v30/closure-dry-run'],
  ['Probe Readiness', '/api/v30/probe-readiness'],
  ['Sports', '/api/v30/sports'],
  ['Source Truth', '/api/v30/source-truth'],
  ['Safety', '/api/v30/safety'],
];

export default function V30Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v16 || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Implemented', mission.implemented_adapter_count ?? '0'],
      ['Deferred', mission.deferred_adapter_spec_count ?? '0'],
      ['Fixtures', mission.fixture_contract_count ?? '0'],
      ['Packets', mission.normalized_evidence_packet_count ?? '0'],
      ['Settlement', mission.settlement_compatible_packet_count ?? '0'],
      ['Dry Scores', mission.dry_run_score_eligible_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Probes', mission.public_probe_ready_count ?? '0'],
      ['Integration', mission.integration_mode_status || 'UNKNOWN'],
      ['Sports', mission.sports_source_mode || 'UNKNOWN'],
      ['Safety', mission.no_adapter_implementation_to_execution_bridge_status || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V30 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V30 In-House Adapters</h1>
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
