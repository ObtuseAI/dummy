import StageDashboard from './StageDashboard';

const endpoints = [["Bridge Controller", "/api/v212/bridge-controller"], ["V211 Baseline", "/api/v212/v211-baseline"], ["First Proof Prerequisite", "/api/v212/first-proof-prerequisite"], ["Reconcile Prerequisite", "/api/v212/reconcile-prerequisite"], ["Forensic Prerequisite", "/api/v212/forensic-prerequisite"], ["Repeat Pilot Readiness Check", "/api/v212/repeat-pilot-readiness-check"], ["Controlled Session Readiness Check", "/api/v212/controlled-session-readiness-check"], ["Scale Readiness Check", "/api/v212/scale-readiness-check"], ["Autonomy Readiness Check", "/api/v212/autonomy-readiness-check"], ["Route State", "/api/v212/route-state"], ["No Submit Proof", "/api/v212/no-submit-proof"], ["No Scale Proof", "/api/v212/no-scale-proof"], ["No Autonomy Proof", "/api/v212/no-autonomy-proof"], ["Readiness Governor", "/api/v212/readiness-governor"], ["Execution Lock", "/api/v212/execution-lock"], ["Mission State", "/api/v212/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Bridge", "bridge_controller_status"], ["Route", "route_state"], ["Live Orders", "live_orders"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V212Dashboard() {
  return <StageDashboard title="Dummy V212 Repeat/Session Bridge" endpoints={endpoints} missionKey="dummy_mission_state_report_v198" summaryFields={summaryFields} />;
}
