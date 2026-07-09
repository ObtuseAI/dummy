import StageDashboard from './StageDashboard';

const endpoints = [["Production Hardening Controller", "/api/v193/production-hardening-controller"], ["V192 Baseline", "/api/v193/v192-baseline"], ["Risk Lock Recheck", "/api/v193/risk-lock-recheck"], ["Abstention Lock Recheck", "/api/v193/abstention-lock-recheck"], ["Session Lock Recheck", "/api/v193/session-lock-recheck"], ["Pilot Proof Lock Recheck", "/api/v193/pilot-proof-lock-recheck"], ["Scale Lock Recheck", "/api/v193/scale-lock-recheck"], ["Autonomy Lock Recheck", "/api/v193/autonomy-lock-recheck"], ["Broker Contact Lock Recheck", "/api/v193/broker-contact-lock-recheck"], ["Live Submit Caps Immutability Recheck", "/api/v193/live-submit-caps-immutability-recheck"], ["Approval File Write Lock Recheck", "/api/v193/approval-file-write-lock-recheck"], ["Stop Policy Update", "/api/v193/stop-policy-update"], ["Repair Recommendation Map", "/api/v193/repair-recommendation-map"], ["No Submit Proof", "/api/v193/no-submit-proof"], ["Readiness Governor", "/api/v193/readiness-governor"], ["Execution Lock", "/api/v193/execution-lock"], ["Mission State", "/api/v193/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Production Hardening", "production_hardening_controller_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Caps Modified", "caps_modified"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V193Dashboard() {
  return <StageDashboard title="Dummy V193 Production Hardening V6" endpoints={endpoints} missionKey="dummy_mission_state_report_v179" summaryFields={summaryFields} />;
}
