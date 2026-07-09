import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Multi-Cycle Expansion Controller', '/api/v41/multi-cycle-expansion-controller'],
  ['Exact Gate V9', '/api/v41/exact-gate'],
  ['V40 Baseline', '/api/v41/v40-baseline'],
  ['Probe Expansion', '/api/v41/probe-expansion'],
  ['Freshness Dedupe', '/api/v41/freshness-dedupe'],
  ['Real Evidence Ledger', '/api/v41/real-evidence-ledger'],
  ['Settlement Expansion', '/api/v41/settlement-expansion'],
  ['Observation Expansion', '/api/v41/observation-expansion'],
  ['Real Live Score Expansion', '/api/v41/real-live-score-expansion'],
  ['Calibration Deepening', '/api/v41/calibration-deepening'],
  ['Source Truth V22', '/api/v41/source-truth-v22'],
  ['No-Trade Discipline', '/api/v41/no-trade-discipline'],
  ['Market-Class Scoreboard', '/api/v41/market-class-scoreboard'],
  ['Readiness Ladder', '/api/v41/readiness-ladder'],
  ['Next Action', '/api/v41/next-action'],
  ['Audit Ledger', '/api/v41/audit-ledger'],
  ['Mission State V41', '/api/v41/mission-state'],
];

export default function V41Dashboard() {
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
    const mission = data['Mission State V41']?.dummy_mission_state_report_v27 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['Gate', mission.exact_gate_status || 'UNKNOWN'],
      ['V40 Baseline', mission.v40_baseline_status || 'UNKNOWN'],
      ['V40 Scores', mission.v40_cumulative_real_scored_count ?? 0],
      ['V41 Cycles', mission.v41_probe_cycle_count ?? 0],
      ['V41 Probes', mission.v41_new_real_probe_count ?? 0],
      ['V41 Evidence', mission.v41_new_evidence_count ?? 0],
      ['Duplicates/Stale', mission.v41_duplicate_stale_excluded_count ?? 0],
      ['V41 Settlement', mission.v41_new_settlement_compatible_count ?? 0],
      ['V41 Observed', mission.v41_new_observed_count ?? 0],
      ['V41 Scores', mission.v41_new_real_scored_count ?? 0],
      ['Cumulative Evidence', mission.cumulative_evidence_count ?? 0],
      ['Cumulative Scores', mission.cumulative_real_scored_count ?? 0],
      ['Calibration Tier', mission.calibration_tier || 'UNKNOWN'],
      ['Source Truth', mission.source_truth_v22_status || 'UNKNOWN'],
      ['No-Trade', mission.no_trade_discipline_v2_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_ladder_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
      ['Live Submit', mission.live_submit_disabled ? 'DISABLED' : 'FAIL'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'FAIL'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V41 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V41 Bounded Real Sample Expansion</h1>
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
