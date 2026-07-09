import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Workflow Kernel', '/api/v37/workflow-kernel'],
  ['Task Queue', '/api/v37/task-queue'],
  ['Next Action Selector', '/api/v37/next-action'],
  ['Build Verify Repair Loop', '/api/v37/build-verify-repair'],
  ['Regression Orchestrator', '/api/v37/regression-orchestrator'],
  ['Report Dashboard Sync', '/api/v37/report-dashboard-sync'],
  ['FAIL Escalation Guard', '/api/v37/fail-escalation'],
  ['Exact-Gated Real Probe Workflow', '/api/v37/real-probe-workflow'],
  ['Evidence Closure Workflow', '/api/v37/evidence-closure'],
  ['Source Truth Workflow', '/api/v37/source-truth-workflow'],
  ['Operator Action Packet', '/api/v37/operator-actions'],
  ['Workflow Scoreboard', '/api/v37/workflow-scoreboard'],
  ['Mission State V37', '/api/v37/mission-state'],
];

export default function V37Dashboard() {
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
    const mission = data['Mission State V37']?.dummy_mission_state_report_v23 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Gate', mission.exact_probe_gate_status || 'UNKNOWN'],
      ['Probe Readiness', mission.real_probe_readiness_status || 'UNKNOWN'],
      ['Evidence', mission.real_evidence_count ?? 0],
      ['Observed', mission.observed_count ?? 0],
      ['Live Scores', mission.live_scored_count ?? 0],
      ['Fake Pipeline', mission.fake_pipeline_score_count ?? 0],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
      ['No Execution Bridge', mission.no_execution_bridge_status || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V37 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V37 Autonomous Workflow</h1>
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
