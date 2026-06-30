import { useStatus } from '../hooks/useStatus';

export default function Home() {
  const status = useStatus();
  if (!status) return <div>Loading...</div>;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card label="Mode" value={status.mode} />
      <Card label="Kill Switch" value={status.kill_switch_active ? 'ACTIVE' : 'Inactive'} />
      <Card label="Emergency Stop" value={status.emergency_stop_active ? 'ACTIVE' : 'Inactive'} />
      <Card label="Kalshi Connected" value={status.kalshi_connected ? 'Yes' : 'No'} />
      <Card label="Balance (¢)" value={status.balance_cents} />
      <Card label="Daily Loss (¢)" value={status.daily_loss_cents} />
      <Card label="Total Exposure (¢)" value={status.total_exposure_cents} />
      <Card label="Open Orders" value={(status.open_orders || []).length} />
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
