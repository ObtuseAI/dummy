import StageDashboard from './StageDashboard';

const endpoints = [["Autonomy Rehearsal Controller", "/api/v192/autonomy-rehearsal-controller"], ["V191 Baseline", "/api/v192/v191-baseline"], ["Rehearsal Session Id", "/api/v192/rehearsal-session-id"], ["Shadow Candidate Sequence", "/api/v192/shadow-candidate-sequence"], ["Autonomous Abstain Lock Escalate Loop", "/api/v192/autonomous-abstain-lock-escalate-loop"], ["Hypothetical Trade Candidate Records", "/api/v192/hypothetical-trade-candidate-records"], ["Hypothetical Per Order Approval Checks", "/api/v192/hypothetical-per-order-approval-checks"], ["Hypothetical Risk Stops", "/api/v192/hypothetical-risk-stops"], ["Hypothetical Reconcile Schema", "/api/v192/hypothetical-reconcile-schema"], ["Dry Live Firewall Proof", "/api/v192/dry-live-firewall-proof"], ["No Broker Payload Proof", "/api/v192/no-broker-payload-proof"], ["No Firewall Submit Call Proof", "/api/v192/no-firewall-submit-call-proof"], ["No Account Private Data Proof", "/api/v192/no-account-private-data-proof"], ["No Scale Proof", "/api/v192/no-scale-proof"], ["Readiness Governor", "/api/v192/readiness-governor"], ["Execution Lock", "/api/v192/execution-lock"], ["Mission State", "/api/v192/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Rehearsal Session", "autonomy_rehearsal_controller_status"], ["Autonomous Trading", "autonomous_trading_enabled"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V192Dashboard() {
  return <StageDashboard title="Dummy V192 Guarded Autonomy Rehearsal Session" endpoints={endpoints} missionKey="dummy_mission_state_report_v178" summaryFields={summaryFields} />;
}
