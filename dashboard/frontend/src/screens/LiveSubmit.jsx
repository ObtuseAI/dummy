import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function LiveSubmit() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/v4/live-submit/status')
      .then(setStatus)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Live Submit</h1>
      {status ? (
        <div className="bg-gray-800 rounded p-4">
          <div className="flex gap-4 mb-4">
            <div className="p-4 bg-gray-900 rounded">
              <div className="text-sm text-gray-400">Enabled</div>
              <div className={`text-2xl font-bold ${status.enabled ? 'text-green-400' : 'text-red-400'}`}>
                {status.enabled ? 'Yes' : 'No'}
              </div>
            </div>
            <div className="p-4 bg-gray-900 rounded">
              <div className="text-sm text-gray-400">Config File Present</div>
              <div className="text-2xl font-bold">{status.file_present ? 'Yes' : 'No'}</div>
            </div>
          </div>
          <p className="text-sm text-gray-400">
            Live order submission is only enabled when the operator explicitly sets
            <code className="mx-1">configs/live_submit.json</code>
            to <code>{`{"enabled": true}`}</code>.
          </p>
          <pre className="mt-4 bg-gray-900 p-3 rounded text-xs overflow-x-auto">{JSON.stringify(status, null, 2)}</pre>
        </div>
      ) : (
        <p className="text-sm text-gray-400">Loading...</p>
      )}
    </div>
  );
}
