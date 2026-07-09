import { useEffect, useState } from 'react';
import { fetchJson } from './hooks/useApi';

export default function V8Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [
          status,
          providers,
          smoke,
          promptFirewall,
          outputFirewall,
          forecasts,
          calibration,
          governor,
          disagreement,
          rehearsal,
          proofReports,
        ] = await Promise.all([
          fetchJson('/v8/status'),
          fetchJson('/v8/model-providers'),
          fetchJson('/v8/live-smoke'),
          fetchJson('/v8/prompt-firewall'),
          fetchJson('/v8/output-firewall'),
          fetchJson('/v8/forecast-opinions'),
          fetchJson('/v8/calibration'),
          fetchJson('/v8/strategy-governor'),
          fetchJson('/v8/disagreement'),
          fetchJson('/v8/firewall-rehearsal'),
          fetchJson('/v8/proof-reports'),
        ]);
        setData({
          status,
          providers,
          smoke,
          promptFirewall,
          outputFirewall,
          forecasts,
          calibration,
          governor,
          disagreement,
          rehearsal,
          proofReports,
        });
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="p-4">Loading V8 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-6">
      <h1 className="text-2xl font-bold">Dummy V8 Dashboard</h1>
      <Section title="Status" data={data.status} />
      <Section title="Model Providers" data={data.providers} />
      <Section title="Live Model Smoke" data={data.smoke} />
      <Section title="Prompt Firewall V2" data={data.promptFirewall} />
      <Section title="Output Firewall" data={data.outputFirewall} />
      <Section title="Forecast Opinions" data={data.forecasts} />
      <Section title="Calibration V2" data={data.calibration} />
      <Section title="Strategy Governor" data={data.governor} />
      <Section title="Hybrid Disagreement V2" data={data.disagreement} />
      <Section title="Firewall Rehearsal V2" data={data.rehearsal} />
      <Section title="Proof Reports" data={data.proofReports} />
    </div>
  );
}

function Section({ title, data }) {
  return (
    <div className="bg-gray-800 rounded p-4">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <pre className="text-sm overflow-auto max-h-64 bg-gray-900 p-2 rounded">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
