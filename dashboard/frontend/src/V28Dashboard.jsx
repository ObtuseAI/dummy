import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v28/mission-state'],
  ['Integration Gate', '/api/v28/integration-gate'],
  ['Public Probes', '/api/v28/public-probes'],
  ['Observation Closure', '/api/v28/observation-closure'],
  ['Sports', '/api/v28/sports'],
  ['OSS Gap Fill', '/api/v28/oss-gap-fill'],
  ['Safety', '/api/v28/safety'],
];

export default function V28Dashboard() {
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
    const mission = data['Mission State']?.dummy_mission_state_report_v14 || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Integration', mission.integration_enabled_state || 'UNKNOWN'],
      ['Probes', mission.public_probe_runner_status || 'UNKNOWN'],
      ['OSS Repos', mission.github_candidate_count ?? '0'],
      ['Due', mission.due_forecast_count ?? '0'],
      ['Observed', mission.observed_forecast_count ?? '0'],
      ['Live Scores', mission.live_scored_count ?? '0'],
      ['Unresolved', mission.live_unresolved_count ?? '0'],
      ['Sports', mission.sports_source_mode || 'UNKNOWN'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
      ['Safety', mission.no_direct_order_bypass_status || 'UNKNOWN'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V28 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V28 Observation Closure</h1>
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
