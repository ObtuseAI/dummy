import { useEffect, useState } from 'react';
import { apiUrl, fetchJson } from './useApi';

export function useStatus() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    let stopped = false;
    let ws;
    let reconnectTimer;
    let reconnectDelay = 1000;
    const refresh = () => fetchJson('/status').then(setStatus).catch(() => {});
    const connect = () => {
      const endpoint = new URL(apiUrl('/ws/status'), window.location.href);
      endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(endpoint.toString());
      ws.onopen = () => { reconnectDelay = 1000; };
      ws.onmessage = e => {
        try { setStatus(s => ({ ...s, ...JSON.parse(e.data) })); } catch { /* malformed update */ }
      };
      ws.onclose = () => {
        if (!stopped) {
          reconnectTimer = window.setTimeout(connect, reconnectDelay);
          reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        }
      };
    };
    refresh();
    const poll = window.setInterval(refresh, 15000);
    connect();
    return () => {
      stopped = true;
      window.clearInterval(poll);
      window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);
  return status;
}
