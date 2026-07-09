import StageDashboard from './StageDashboard';

const endpoints = [["One Command Dry Pipeline Controller", "/api/v227/one-command-dry-pipeline-controller"], ["V226 Baseline", "/api/v227/v226-baseline"], ["Dry Stage Manifest Intake", "/api/v227/dry-stage-manifest-intake"], ["Dry Stage Resolver", "/api/v227/dry-stage-resolver"], ["Dry Stage Arming", "/api/v227/dry-stage-arming"], ["Dry Stage Live Proof", "/api/v227/dry-stage-live-proof"], ["Dry Stage Reconcile Forensic", "/api/v227/dry-stage-reconcile-forensic"], ["Simulated Pipeline Schema", "/api/v227/simulated-pipeline-schema"], ["No Firewall Submit Proof", "/api/v227/no-firewall-submit-proof"], ["No Broker Payload Proof", "/api/v227/no-broker-payload-proof"], ["No Account Access Proof", "/api/v227/no-account-access-proof"], ["No File Write Proof", "/api/v227/no-file-write-proof"], ["Readiness Governor", "/api/v227/readiness-governor"], ["Execution Lock", "/api/v227/execution-lock"], ["Mission State", "/api/v227/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Dry Pipeline", "one_command_dry_pipeline_controller_status"], ["Broker Contacted", "real_broker_contacted"], ["Live Orders", "total_real_live_orders_submitted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V227Dashboard() {
  return <StageDashboard title="Dummy V227 One Command Dry Pipeline Zero Broker Contact" endpoints={endpoints} missionKey="dummy_mission_state_report_v213" summaryFields={summaryFields} />;
}
