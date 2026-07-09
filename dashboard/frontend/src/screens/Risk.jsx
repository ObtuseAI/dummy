import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Risk() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/risk').then(setData); }, []);
  if (!data) return <div className="p-4">Loading...</div>;

  const caps = data.caps || {};
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Risk & Caps</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Object.entries(caps).map(([k, v]) => (
          <div key={k} className="bg-gray-800 p-3 rounded text-sm">
            <div className="text-gray-400">{k}</div>
            <div className="font-mono">{String(v)}</div>
          </div>
        ))}
      </div>
      <div className="bg-gray-800 p-4 rounded">
        <div className="text-gray-400">Daily Loss (¢)</div>
        <div className="text-xl font-bold">{data.daily_loss_cents}</div>
      </div>
    </div>
  );
}
