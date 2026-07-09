import StageDashboard from './StageDashboard';

const endpoints = [["Execute Once Handoff Controller", "/api/v241/execute-once-handoff-controller"], ["V240 Baseline", "/api/v241/v240-baseline"], ["Exact Command", "/api/v241/exact-command"], ["Required Env Gate", "/api/v241/required-env-gate"], ["Required Manifest", "/api/v241/required-manifest"], ["Required Adapter Injection", "/api/v241/required-adapter-injection"], ["Proof Target", "/api/v241/proof-target"], ["Expected Fail Closed State", "/api/v241/expected-fail-closed-state"], ["Expected Success State", "/api/v241/expected-success-state"], ["Default No Submit Check", "/api/v241/default-no-submit-check"], ["No Approval File Write Proof", "/api/v241/no-approval-file-write-proof"], ["No Runtime Approvals Proof", "/api/v241/no-runtime-approvals-proof"], ["No Submit Proof", "/api/v241/no-submit-proof"], ["Readiness Governor", "/api/v241/readiness-governor"], ["Execution Lock", "/api/v241/execution-lock"], ["Mission State", "/api/v241/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Execute-Once Handoff", "execute_once_handoff_controller_status"], ["Live Orders", "total_real_live_orders_submitted"], ["Approval Files Written", "approval_files_written"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V241Dashboard() {
  return <StageDashboard title="Dummy V241 Execute Once Handoff V2 Operator Final Command No Submit Default" endpoints={endpoints} missionKey="dummy_mission_state_report_v227" summaryFields={summaryFields} />;
}
