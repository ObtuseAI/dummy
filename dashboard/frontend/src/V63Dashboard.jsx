import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Dry-Submit Schema Gate', '/api/v63/dry-submit-schema-gate'],
  ['Shadow Packet Schema Gate', '/api/v63/shadow-packet-schema-gate'],
  ['V62 Baseline', '/api/v63/v62-baseline'],
  ['Schema-Only Artifact Validator', '/api/v63/schema-only-artifact-validator'],
  ['Broker-Submit Denial Proof', '/api/v63/broker-submit-denial-proof'],
  ['No-Market-Order Validator', '/api/v63/no-market-order-validator'],
  ['No-Live-Submit Validator', '/api/v63/no-live-submit-validator'],
  ['Canary Non-Execution Validator V13', '/api/v63/canary-nonexecution-validator-v13'],
  ['Readiness Governor V23', '/api/v63/readiness-governor'],
  ['Execution Lock V22', '/api/v63/execution-lock'],
  ['Mission State V63', '/api/v63/mission-state'],
];

export default function V63Dashboard() {
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
    const mission = data['Mission State V63']?.dummy_mission_state_report_v49 || {};
    return [
      ['Mission', mission.mission_state_verdict || mission.verdict || 'UNKNOWN'],
      ['V62 Baseline', mission.v62_baseline_status || 'UNKNOWN'],
      ['Dry-Submit Schema', mission.dry_submit_schema_gate_status || 'UNKNOWN'],
      ['Shadow Packet Schema', mission.shadow_packet_schema_gate_status || 'UNKNOWN'],
      ['Broker-Submit Denial', mission.broker_submit_denial_proof_status || 'UNKNOWN'],
      ['No-Market-Order', mission.no_market_order_validator_status || 'UNKNOWN'],
      ['No-Live-Submit', mission.no_live_submit_validator_status || 'UNKNOWN'],
      ['Canary', mission.canary_nonexecution_validator_v13_status || 'UNKNOWN'],
      ['Readiness', mission.readiness_governor_v23_status || 'UNKNOWN'],
      ['Execution Lock', mission.execution_lock_deep_recheck_v22_status || 'UNKNOWN'],
      ['Next Action', mission.current_next_action || 'UNKNOWN'],
      ['Blockers', (mission.current_blockers || []).join(', ') || 'NONE'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V63 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V63 Dry-Submit / Shadow Packet Schema Gate</h1>
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
