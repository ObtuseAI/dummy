import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Gate Runtime', '/api/v38/gate-runtime'],
  ['Probe Run', '/api/v38/probe-run'],
  ['Evidence Chain', '/api/v38/evidence-chain'],
  ['Settlement Closure', '/api/v38/settlement-closure'],
  ['Live Score', '/api/v38/live-score'],
  ['Calibration Source Truth', '/api/v38/calibration-source-truth'],
  ['Operator Packet', '/api/v38/operator-packet'],
  ['API Surface', '/api/v38/api-surface'],
  ['Dashboard Contract', '/api/v38/dashboard'],
  ['Safety', '/api/v38/safety'],
  ['Mission State V38', '/api/v38/mission-state'],
];

export default function V38Dashboard() {
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
    const mission = data['Mission State V38']?.dummy_mission_state_report_v24 || {};
    const packet = data['Operator Packet']?.v38_operator_packet_v1_report || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Milestone', mission.milestone_status || 'UNKNOWN'],
      ['Next Action', mission.next_action || mission.current_next_action || 'UNKNOWN'],
      ['Gate', mission.exact_probe_gate_status || 'UNKNOWN'],
      ['Probe Runs', mission.real_probe_run_count ?? 0],
      ['Evidence', mission.real_evidence_count ?? 0],
      ['Settlement', mission.settlement_compatible_evidence_count ?? 0],
      ['Observed', mission.observed_real_live_public_count ?? 0],
      ['Live Scores', mission.real_scored_count ?? 0],
      ['Fake Pipeline', mission.fake_pipeline_score_count ?? 0],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Operator Packet', Object.keys(packet.operator_packet || {}).length ? 'REQUIRED' : 'NOT NEEDED'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V38 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V38 Readonly Probe Completion</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-7">
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

