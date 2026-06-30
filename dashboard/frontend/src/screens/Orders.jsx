import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Orders() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/orders').then(setData); }, []);
  if (!data) return <div>Loading...</div>;
  return <pre className="text-sm">{JSON.stringify(data, null, 2)}</pre>;
}
