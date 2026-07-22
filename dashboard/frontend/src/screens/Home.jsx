import { useEffect, useState } from 'react';
import { useStatus } from '../hooks/useStatus';
import { fetchJson } from '../hooks/useApi';
import { arrayCountOrUnknown, booleanLabel, valueOrUnknown } from '../components/TruthValue';

export default function Home() {
  const status = useStatus();
  const [kalshi, setKalshi] = useState(null);
  const [kalshiError, setKalshiError] = useState(null);
  useEffect(() => {
    fetchJson('/api/read-only/kalshi/status').then(setKalshi).catch(error => setKalshiError(error.message));
  }, []);
  if (!status) return <div>Loading...</div>;
  return (
    <div className="space-y-5">
      <div className="rounded border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
        Local runtime and durable risk observations only. The home screen does not contact a broker; connection and balance fields remain unverified unless a timestamped witness is available.
        {kalshiError && <div className="mt-1 text-amber-300">Kalshi status unavailable: {kalshiError}</div>}
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Mode" value={status.mode} />
        <Card label="Kill Switch" value={booleanLabel(status.kill_switch_active, 'ACTIVE', 'INACTIVE')} />
        <Card label="Emergency Stop" value={booleanLabel(status.emergency_stop_active, 'ACTIVE', 'INACTIVE')} />
        <Card label="Broker connection verified" value={booleanLabel(kalshi?.connection_verified, 'YES', 'NO')} />
        <Card label="Runtime connection flag (unverified)" value={booleanLabel(kalshi?.runtime_connected_flag, 'TRUE', 'FALSE')} />
        <Card label="Credentials present" value={booleanLabel(kalshi?.credentials_present)} />
        <Card label="Stored balance (¢, unverified)" value={kalshi?.balance_cents} />
        <Card label="Daily Loss (¢, local state)" value={status.daily_loss_cents} />
        <Card label="Total Exposure (¢, durable state)" value={status.total_exposure_cents} />
        <Card label="Open Orders" value={arrayCountOrUnknown(status.open_orders)} />
        <Card label="Open Positions" value={arrayCountOrUnknown(status.open_positions)} />
        <Card label="Exposure state" value={status.exposure_state_status} />
      </div>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div className="p-4 bg-gray-800 rounded">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xl font-bold">{String(valueOrUnknown(value))}</div>
    </div>
  );
}
