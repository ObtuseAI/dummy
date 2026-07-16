import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Run Controller', '/api/v39/run-controller'],
  ['Exact Gate', '/api/v39/exact-gate'],
  ['V38 Rerun', '/api/v39/v38-rerun'],
  ['Real Public Source Run', '/api/v39/real-public-source-run'],
  ['Live Public Evidence', '/api/v39/live-public-evidence'],
  ['Settlement Compatible Evidence', '/api/v39/settlement-compatible-evidence'],
  ['Real Due Observation', '/api/v39/real-due-observation'],
  ['First Real Live Score', '/api/v39/first-real-live-score'],
  ['Readonly Live Intelligence', '/api/v39/readonly-live-intelligence'],
  ['First Live Score Milestone', '/api/v39/first-live-score-milestone'],
  ['Live Calibration', '/api/v39/live-calibration'],
  ['Source Truth Real Outcome', '/api/v39/source-truth-real-outcome'],
  ['Completion Repair Selector', '/api/v39/completion-repair-selector'],
  ['Real Run Audit Ledger', '/api/v39/real-run-audit-ledger'],
  ['Mission State V39', '/api/v39/mission-state'],
];

export default function V39Dashboard() {
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
    const mission = data['Mission State V39']?.dummy_mission_state_report_v25 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Probe Runs', mission.real_probe_run_count ?? 0],
      ['Evidence', mission.real_evidence_count ?? 0],
      ['Settlement', mission.settlement_compatible_evidence_count ?? 0],
      ['Observed', mission.real_observed_count ?? 0],
      ['Scores', mission.real_scored_count ?? 0],
      ['Fake Pipeline', mission.fake_pipeline_score_count ?? 0],
      ['Readonly Intel', mission.readonly_live_intelligence_status || 'UNKNOWN'],
      ['First Score', mission.first_live_score_milestone_status || 'UNKNOWN'],
      ['Calibration', mission.live_calibration_low_sample_status || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V39 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V39 Readonly Probe Execution</h1>
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
