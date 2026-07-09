import StageDashboard from './StageDashboard';

const endpoints = [["Autonomy Dryrun Controller", "/api/v187/autonomy-dryrun-controller"], ["V186 Baseline", "/api/v187/v186-baseline"], ["Limited Autonomy Dryrun Approval Validator", "/api/v187/limited-autonomy-dryrun-approval-validator"], ["Autonomy Review Approval Validator", "/api/v187/autonomy-review-approval-validator"], ["Broad Fuzzy Approval Rejection", "/api/v187/broad-fuzzy-approval-rejection"], ["Live Submit Disabled Proof", "/api/v187/live-submit-disabled-proof"], ["No Broker Payload Proof", "/api/v187/no-broker-payload-proof"], ["Livebrokerfirewall Submit Denial Proof", "/api/v187/livebrokerfirewall-submit-denial-proof"], ["No Caps Modification Proof", "/api/v187/no-caps-modification-proof"], ["No Approval File Write Proof", "/api/v187/no-approval-file-write-proof"], ["Readiness Governor", "/api/v187/readiness-governor"], ["Execution Lock", "/api/v187/execution-lock"], ["Mission State", "/api/v187/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry-Run Validator", "autonomy_dryrun_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V187Dashboard() {
  return <StageDashboard title="Dummy V187 Limited Autonomy Dry-Run Approval Validator" endpoints={endpoints} missionKey="dummy_mission_state_report_v173" summaryFields={summaryFields} />;
}
