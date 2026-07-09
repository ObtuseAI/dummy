import StageDashboard from './StageDashboard';

const endpoints = [["Route Command Center V2", "/api/v283/route-command-center-v2"], ["V282 Baseline", "/api/v283/v282-baseline"], ["Route State", "/api/v283/route-state"], ["Ui Flags", "/api/v283/ui-flags"], ["No Submit Proof", "/api/v283/no-submit-proof"], ["No Scale Proof", "/api/v283/no-scale-proof"], ["No Autonomy Proof", "/api/v283/no-autonomy-proof"], ["Readiness Governor", "/api/v283/readiness-governor"], ["Execution Lock", "/api/v283/execution-lock"], ["Mission State", "/api/v283/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Route Center", "route_command_center_v2_controller_status"], ["Route", "route_state"], ["Next Action", "current_next_action"]];

export default function V283Dashboard() {
  return <StageDashboard title="Dummy V283 Route Command Center V2" endpoints={endpoints} missionKey="dummy_mission_state_report_v283" summaryFields={summaryFields} />;
}
