import StageDashboard from './StageDashboard';

const endpoints = [["Mode Firewall Controller", "/api/v148/mode-firewall-controller"], ["V147 Baseline", "/api/v148/v147-baseline"], ["Dry Mode Enum", "/api/v148/dry-mode-enum"], ["Live Mode Enum", "/api/v148/live-mode-enum"], ["Prohibited Crossover Matrix", "/api/v148/prohibited-crossover-matrix"], ["Dry Submit Cannot Call Broker Proof", "/api/v148/dry-submit-cannot-call-broker-proof"], ["Live Submit Requires Full Authority Proof", "/api/v148/live-submit-requires-full-authority-proof"], ["Dry Artifacts Not Broker Payloads Proof", "/api/v148/dry-artifacts-not-broker-payloads-proof"], ["Live Payload Not In Dry Mode Proof", "/api/v148/live-payload-not-in-dry-mode-proof"], ["No Submit Default Proof", "/api/v148/no-submit-default-proof"], ["Readiness Governor", "/api/v148/readiness-governor"], ["Execution Lock", "/api/v148/execution-lock"], ["Mission State", "/api/v148/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Mode Firewall", "mode_firewall_controller_status"], ["Mode", "mode"], ["Broker Contacted", "broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V148Dashboard() {
  return <StageDashboard title="Dummy V148 Dry/Live Mode Firewall" endpoints={endpoints} missionKey="dummy_mission_state_report_v134" summaryFields={summaryFields} />;
}
