import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v19/mission-state'],
  ['Source Activation', '/api/v19/source-activation'],
  ['Domain Watchlist', '/api/v19/domain-watchlist'],
  ['Domain Scan Cycle', '/api/v19/domain-scan-cycle'],
  ['Real Evidence Packets', '/api/v19/real-evidence-packets'],
  ['Forecast Activation', '/api/v19/forecast-activation'],
  ['Outcome Observer V2', '/api/v19/outcome-observer-v2'],
  ['Calibration Bootstrap', '/api/v19/calibration-bootstrap'],
  ['Autonomous Compounding', '/api/v19/autonomous-compounding'],
  ['Domain Scoreboard V2', '/api/v19/domain-scoreboard-v2'],
];

export default function V19Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const responses = await Promise.all(endpoints.map(([, path]) => fetchJson(path)));
        setData(Object.fromEntries(endpoints.map(([title], index) => [title, responses[index]])));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const summary = useMemo(() => {
    const mission = data['Mission State']?.mission_state || {};
    const activation = data['Source Activation']?.source_activation || {};
    const packets = data['Real Evidence Packets']?.real_evidence_packets || {};
    const forecast = data['Forecast Activation']?.forecast_activation || {};
    const compounding = data['Autonomous Compounding']?.autonomous_compounding || {};
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Activation', activation.verdict || 'UNKNOWN'],
      ['Real', mission.fixture_vs_real_evidence_split?.real_read_only ?? '0'],
      ['Fixture', mission.fixture_vs_real_evidence_split?.fixture_static ?? '0'],
      ['Packets', packets.packet_count ?? '0'],
      ['Forecasts', forecast.ledger_write_count ?? '0'],
      ['Proposals', compounding.proposal_count ?? '0'],
      ['Submit', mission.live_submit_disabled ? 'DISABLED' : 'CHECK'],
      ['Caps', mission.caps_unchanged ? 'UNCHANGED' : 'CHECK'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V19 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V19 Source Activation</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {summary.map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded p-3 border border-gray-700">
            <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
            <div className="mt-1 text-base font-semibold text-white break-words">{String(value)}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {endpoints.map(([title]) => (
          <Section key={title} title={title} data={data[title]} />
        ))}
      </div>
    </div>
  );
}

function Section({ title, data }) {
  return (
    <div className="bg-gray-800 rounded p-4 border border-gray-700">
      <h2 className="text-base font-semibold mb-2">{title}</h2>
      <pre className="text-xs overflow-auto max-h-80 bg-gray-900 p-2 rounded">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
