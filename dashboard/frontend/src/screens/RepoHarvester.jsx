import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function RepoHarvester() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/repo-harvester/status').then(setData); }, []);
  if (!data) return <div className="p-4">Loading...</div>;

  const scan = data.v2_source_scan || {};
  const adapters = data.adapters || {};
  const firewall = data.live_firewall_status || {};
  const findings = data.firewall_bypass_findings || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">V2 Repo Source Scan</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="Repos Scanned" value={`${scan.repos_scanned} / ${scan.repos_in_manifest}`} />
        <Card label="Files Scanned" value={scan.total_files_scanned} />
        <Card label="Accepted Adapters" value={adapters.accepted} />
        <Card label="Rejected Repos" value={adapters.rejected} />
        <Card label="Direct Order Risks" value={findings.direct_order_count} />
        <Card label="Secret Risks" value={findings.secret_risk_count} />
        <Card label="Mode" value={firewall.mode} />
        <Card label="Kill Switch" value={firewall.kill_switch_active ? 'ACTIVE' : 'Inactive'} />
        <Card label="Emergency Stop" value={firewall.emergency_stop_active ? 'ACTIVE' : 'Inactive'} />
      </div>

      <Section title="Verdict Counts">
        <KeyValueList obj={scan.verdict_counts || {}} />
      </Section>

      <Section title="Source-Scan Findings">
        <KeyValueList obj={scan.finding_category_repo_counts || {}} />
      </Section>

      <Section title="Blocked Order Reasons (repo-derived direct-order / secret risk)">
        {data.blocked_order_reasons?.length ? (
          <ul className="list-disc pl-5 text-sm space-y-1">
            {data.blocked_order_reasons.map(r => <li key={r}>{r}</li>)}
          </ul>
        ) : <p className="text-sm text-gray-400">None recorded</p>}
      </Section>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-4 bg-gray-800 rounded">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xl font-bold">{String(value)}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
    </div>
  );
}

function KeyValueList({ obj }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
      {Object.entries(obj).map(([k, v]) => (
        <div key={k} className="flex justify-between bg-gray-900 p-2 rounded">
          <span className="text-gray-400">{k}</span>
          <span className="font-mono">{String(v)}</span>
        </div>
      ))}
    </div>
  );
}
