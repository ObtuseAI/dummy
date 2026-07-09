import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v18/mission-state'],
  ['Domain Intelligence', '/api/v18/domain-intelligence'],
  ['Research Packets', '/api/v18/research-packets'],
  ['Evidence Stacks', '/api/v18/evidence-stacks'],
  ['Source Truth', '/api/v18/source-truth'],
  ['Domain Baselines', '/api/v18/domain-baselines'],
  ['Settlement Mapper', '/api/v18/settlement-mapper'],
  ['Domain Scoreboard', '/api/v18/domain-scoreboard'],
];

export default function V18Dashboard() {
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
    const intelligence = data['Domain Intelligence']?.domain_intelligence || {};
    const packets = data['Research Packets']?.research_packets || {};
    const baselines = data['Domain Baselines']?.domain_baselines || {};
    const settlement = data['Settlement Mapper']?.settlement_mapper || {};
    const scoreboard = data['Domain Scoreboard']?.domain_scoreboard || {};
    return [
      ['Mission', mission.mission_state_verdict || 'UNKNOWN'],
      ['Domains', intelligence.domain_count ?? '0'],
      ['Packets', packets.packet_count ?? '0'],
      ['Baselines', baselines.ledger_snapshot_count ?? '0'],
      ['Settlement', settlement.verdict || 'UNKNOWN'],
      ['Fixture', mission.fixture_evidence_count ?? '0'],
      ['Real', mission.real_evidence_count ?? '0'],
      ['Scoreboard', scoreboard.verdict || 'UNKNOWN'],
      ['Submit', mission.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'CHECK'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V18 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V18 Domain Intelligence</h1>
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
