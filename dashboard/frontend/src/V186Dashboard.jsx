import StageDashboard from './StageDashboard';

const endpoints = [["Session Authority Controller", "/api/v186/session-authority-controller"], ["V185 Baseline", "/api/v186/v185-baseline"], ["Controlled Operation Approval Validator", "/api/v186/controlled-operation-approval-validator"], ["Controlled Session Approval Validator", "/api/v186/controlled-session-approval-validator"], ["First Pilot Proof Checker", "/api/v186/first-pilot-proof-checker"], ["Repeat Pilot Proof Checker", "/api/v186/repeat-pilot-proof-checker"], ["Pilot Pair Proof Checker", "/api/v186/pilot-pair-proof-checker"], ["Live Submit Caps Readonly Checker", "/api/v186/live-submit-caps-readonly-checker"], ["Firewall Adapter Checker", "/api/v186/firewall-adapter-checker"], ["Mode Firewall Checker", "/api/v186/mode-firewall-checker"], ["Candidate Risk Abstention Proof Checker", "/api/v186/candidate-risk-abstention-proof-checker"], ["Approval Hash Only Ledger", "/api/v186/approval-hash-only-ledger"], ["No Approval File Write Proof", "/api/v186/no-approval-file-write-proof"], ["No Submit Proof", "/api/v186/no-submit-proof"], ["Readiness Governor", "/api/v186/readiness-governor"], ["Execution Lock", "/api/v186/execution-lock"], ["Mission State", "/api/v186/mission-state"]];

const summaryFields = [["Mission", "mission_state_verdict"], ["Session Authority", "session_authority_controller_status"], ["Live Orders", "live_orders"], ["Broker Contacted", "real_broker_contacted"], ["Next Action", "current_next_action"], ["Blockers", "current_blockers"]];

export default function V186Dashboard() {
  return <StageDashboard title="Dummy V186 Controlled Session Authority Recheck" endpoints={endpoints} missionKey="dummy_mission_state_report_v172" summaryFields={summaryFields} />;
}
