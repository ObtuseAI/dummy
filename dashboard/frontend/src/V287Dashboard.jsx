import StageDashboard from './StageDashboard';

const endpoints = [["Final Run Appliance Launcher", "/api/v287/final-run-appliance-launcher"], ["V286 Baseline", "/api/v287/v286-baseline"], ["Dry Pipeline", "/api/v287/dry-pipeline"], ["No Submit Proof", "/api/v287/no-submit-proof"], ["No Broker Contact Proof", "/api/v287/no-broker-contact-proof"], ["Readiness Governor", "/api/v287/readiness-governor"], ["Execution Lock", "/api/v287/execution-lock"], ["Mission State", "/api/v287/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Appliance", "final_run_appliance_launcher_controller_status"], ["Next Action", "current_next_action"]];

export default function V287Dashboard() {
  return <StageDashboard title="Dummy V287 Final Run Appliance Launcher" endpoints={endpoints} missionKey="dummy_mission_state_report_v287" summaryFields={summaryFields} />;
}
