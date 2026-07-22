import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel } from '../components/TruthValue';

export default function LiveSubmit() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/api/read-only/live-submit/status')
      .then(setStatus)
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Live Submit</h1>
      <div className="rounded border-2 border-amber-600 bg-amber-950/50 p-4 text-sm text-amber-100">
        A configuration flag is not execution authority. Effective enablement remains UNKNOWN until every canary, cap, approval, risk-state, and central-firewall gate is verified at submission time.
      </div>
      {status ? (
        <div className="bg-gray-800 rounded p-4">
          <div className="flex gap-4 mb-4">
            <div className="p-4 bg-gray-900 rounded">
              <div className="text-sm text-gray-400">Configured flag</div>
              <div className={`text-2xl font-bold ${status.configured_enabled === true ? 'text-amber-300' : status.configured_enabled === false ? 'text-red-400' : 'text-gray-400'}`}>
                {booleanLabel(status.configured_enabled)}
              </div>
            </div>
            <div className="p-4 bg-gray-900 rounded">
              <div className="text-sm text-gray-400">Effective execution</div>
              <div className={`text-2xl font-bold ${status.effective_execution_enabled === true ? 'text-green-400' : status.effective_execution_enabled === false ? 'text-red-400' : 'text-gray-400'}`}>
                {booleanLabel(status.effective_execution_enabled)}
              </div>
            </div>
            <div className="p-4 bg-gray-900 rounded">
              <div className="text-sm text-gray-400">This page authority</div>
              <div className="text-2xl font-bold text-red-400">{booleanLabel(status.execution_authority)}</div>
            </div>
            <div className="p-4 bg-gray-900 rounded">
              <div className="text-sm text-gray-400">Config File Present</div>
              <div className="text-2xl font-bold">{booleanLabel(status.file_present)}</div>
            </div>
          </div>
          <p className="text-sm text-gray-400">
            The operator can request live-submit consideration by explicitly setting
            <code className="mx-1">configs/live_submit.json</code>
            to <code>{`{"enabled": true}`}</code>. That request does not enable submission by itself.
          </p>
          <pre className="mt-4 bg-gray-900 p-3 rounded text-xs overflow-x-auto">{JSON.stringify(status, null, 2)}</pre>
        </div>
      ) : (
        <p className="text-sm text-gray-400">Loading...</p>
      )}
    </div>
  );
}
