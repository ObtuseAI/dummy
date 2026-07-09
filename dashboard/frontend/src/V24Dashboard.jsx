import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from './hooks/useApi';

const endpoints = [
  ['Mission State', '/api/v24/mission-state'],
  ['Open-Source Source Doctrine', '/api/v24/open-source-doctrine'],
  ['Source Universe Reclassification', '/api/v24/source-universe-reclassification'],
  ['Keyless Public Adapter Expansion', '/api/v24/keyless-public-expansion'],
  ['Public Proxy Edge Terrain', '/api/v24/public-proxy-terrain'],
  ['Nasdaq Open Proxy Terrain', '/api/v24/nasdaq-open-proxy'],
  ['Oil Open Proxy Terrain', '/api/v24/oil-open-proxy'],
  ['Open Data Replay Dataset Builder', '/api/v24/open-data-replay'],
  ['Replay Calibration Harness V2', '/api/v24/replay-calibration-v2'],
  ['Open-Source Baseline Lab', '/api/v24/open-source-baseline-lab'],
  ['Keyless Live Forecast Expansion', '/api/v24/keyless-live-forecast-expansion'],
  ['Open-Source Adapter Work Queue', '/api/v24/open-source-adapter-work-queue'],
  ['Optional Premium Feed Demotion', '/api/v24/optional-premium-demotion'],
  ['Open-Source Source Truth V6', '/api/v24/source-truth-v6'],
  ['Forecast Lifecycle V3', '/api/v24/forecast-lifecycle-v3'],
  ['Open-Source Compounding V8', '/api/v24/open-source-compounding-v8'],
  ['Domain Scoreboard V9', '/api/v24/domain-scoreboard-v9'],
];

export default function V24Dashboard() {
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
    return [
      ['Mission', mission.verdict || 'UNKNOWN'],
      ['Keyless Sources', mission.keyless_public_active_count ?? '0'],
      ['Proxy Terrain', mission.public_proxy_terrain_count ?? '0'],
      ['Replay Sets', mission.replay_dataset_count ?? '0'],
      ['Replay Scores', mission.replay_score_count ?? '0'],
      ['Live Forecasts', mission.live_forecast_count ?? '0'],
      ['Unresolved', mission.live_unresolved_count ?? '0'],
      ['No-Trade', mission.no_trade_count ?? '0'],
      ['Premium Optional', mission.optional_premium_blocker_count ?? '0'],
      ['Submit', mission.live_submit_enabled ? 'CHECK' : 'DISABLED'],
      ['Caps', mission.caps_config_status || 'PASS'],
    ];
  }, [data]);

  if (loading) return <div className="p-4">Loading V24 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-5">
      <h1 className="text-2xl font-bold">Dummy V24 Open Public Data Edge</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
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
