import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Markets() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/markets').then(setData); }, []);
  if (!data) return <div>Loading...</div>;
  return <pre className="text-sm">{JSON.stringify(data, null, 2)}</pre>;
}
