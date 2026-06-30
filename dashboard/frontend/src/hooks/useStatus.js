import { useEffect, useState } from 'react';
import { fetchJson } from './useApi';

export function useStatus() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    fetchJson('/status').then(setStatus);
    const ws = new WebSocket('ws://localhost:8000/ws/status');
    ws.onmessage = e => setStatus(s => ({ ...s, ...JSON.parse(e.data) }));
    return () => ws.close();
  }, []);
  return status;
}
