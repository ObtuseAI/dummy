import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Sample Expansion Controller', '/api/v40/sample-expansion-controller'],
  ['Exact Gate V8', '/api/v40/exact-gate'],
  ['V39 Baseline', '/api/v40/v39-baseline'],
  ['Real Public Probe Expansion', '/api/v40/real-public-probe-expansion'],
  ['Expanded Live Evidence', '/api/v40/expanded-live-evidence'],
  ['Expanded Settlement', '/api/v40/expanded-settlement'],
  ['Expanded Observation', '/api/v40/expanded-observation'],
  ['Expanded Real Live Score', '/api/v40/expanded-real-live-score'],
  ['Calibration Growth', '/api/v40/calibration-growth'],
  ['Source Truth V21', '/api/v40/source-truth-v21'],
  ['No-Trade Discipline', '/api/v40/no-trade-discipline'],
  ['Market-Class Scoreboard', '/api/v40/market-class-scoreboard'],
  ['Next Action', '/api/v40/next-action'],
  ['Audit Ledger', '/api/v40/audit-ledger'],
  ['Mission State V40', '/api/v40/mission-state'],
];

export default function V40Dashboard() {
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
    const mission = data['Mission State V40']?.dummy_mission_state_report_v26 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V39 Baseline Scores', mission.v39_baseline_real_scored_count ?? 0],
      ['V40 New Probes', mission.v40_new_real_probe_count ?? 0],
      ['V40 New Evidence', mission.v40_new_evidence_count ?? 0],
      ['V40 Settlement', mission.v40_new_settlement_compatible_count ?? 0],
      ['V40 Observed', mission.v40_new_observed_count ?? 0],
      ['V40 New Scores', mission.v40_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Fake Pipeline', mission.fake_pipeline_score_count ?? 0],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v21_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V40 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V40 Real Sample Expansion</h1>
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
