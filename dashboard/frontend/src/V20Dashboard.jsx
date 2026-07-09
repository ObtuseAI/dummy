import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v20/mission-state'],
  ['Source Universe', '/api/v20/source-universe'],
  ['Source Candidates', '/api/v20/source-candidates'],
  ['GitHub Source Miner', '/api/v20/github-source-miner'],
  ['Approval Gate', '/api/v20/source-approval-gate'],
  ['Official/Public Adapters', '/api/v20/official-public-adapters'],
  ['Licensed Plans', '/api/v20/licensed-adapter-plans'],
  ['Nasdaq Terrain', '/api/v20/nasdaq-direction-terrain'],
  ['Oil Terrain', '/api/v20/oil-direction-terrain'],
  ['Crypto Terrain', '/api/v20/crypto-direction-terrain'],
  ['Weather Terrain', '/api/v20/weather-terrain'],
  ['Sports Terrain', '/api/v20/sports-terrain'],
  ['Evidence Router V2', '/api/v20/evidence-router-v2'],
  ['Research Swarm V2', '/api/v20/research-swarm-v2'],
  ['Forecast Pipeline V2', '/api/v20/forecast-pipeline-v2'],
  ['Source Gap Recommendations', '/api/v20/source-gap-recommendations'],
  ['Compounding Control Plane V3', '/api/v20/compounding-control-plane-v3'],
  ['Domain Scoreboard V4', '/api/v20/domain-scoreboard-v4'],
];

export default function V20Dashboard() {
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
    const universe = data['Source Universe']?.source_universe || {};
    const miner = data['GitHub Source Miner']?.github_source_miner || {};
    const scoreboard = data['Domain Scoreboard V4']?.domain_scoreboard_v4 || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Universe', mission.source_universe_status || universe.verdict || 'UNKNOWN'],
      ['Sources', universe.source_count ?? '0'],
      ['GitHub Mode', mission.github_miner_mode || miner.mode || 'UNKNOWN'],
      ['Real', mission.real_vs_fixture_split?.real_read_only ?? '0'],
      ['Fixture', mission.real_vs_fixture_split?.fixture_static ?? scoreboard.fixture_total ?? '0'],
      ['Submit', mission.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'CHECK'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V20 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V20 Source Universe</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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

