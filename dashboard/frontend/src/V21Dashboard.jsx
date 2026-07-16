import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v21/mission-state'],
  ['Activation Policy', '/api/v21/source-activation-policy'],
  ['Approval Cockpit', '/api/v21/source-approval-cockpit'],
  ['Official Public Activation', '/api/v21/official-public-activation'],
  ['EIA Energy', '/api/v21/eia-energy'],
  ['NWS Weather', '/api/v21/nws-weather'],
  ['Crypto Public Exchange', '/api/v21/crypto-public-exchange'],
  ['Finance Macro Official', '/api/v21/finance-macro-official'],
  ['Nasdaq Bootstrap', '/api/v21/nasdaq-bootstrap'],
  ['Oil Bootstrap', '/api/v21/oil-bootstrap'],
  ['Licensed Acquisition', '/api/v21/licensed-acquisition'],
  ['GitHub Miner', '/api/v21/github-miner'],
  ['Evidence Router V3', '/api/v21/evidence-router-v3'],
  ['Forecast Pipeline V3', '/api/v21/forecast-pipeline-v3'],
  ['Compounding V4', '/api/v21/compounding-v4'],
  ['Domain Scoreboard V5', '/api/v21/domain-scoreboard-v5'],
];

export default function V21Dashboard() {
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
    const activation = data['Official Public Activation']?.official_public_activation || {};
    const router = data['Evidence Router V3']?.evidence_role || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Activated', activation.activated_source_count ?? mission.activated_source_count ?? '0'],
      ['Blocked', activation.blocked_source_count ?? mission.blocked_source_count ?? '0'],
      ['GitHub', mission.github_miner_mode || 'UNKNOWN'],
      ['Context', router.context_vs_edge_split?.context ?? mission.context_vs_edge_split?.context ?? '0'],
      ['Edge', router.context_vs_edge_split?.edge ?? mission.context_vs_edge_split?.edge ?? '0'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V21 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V21 Source Activation</h1>
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
