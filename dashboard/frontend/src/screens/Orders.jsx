import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function Orders() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchJson('/orders').then(setData); }, []);
  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Orders</h1>
      {(data.orders || []).length ? (
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-800">
            <tr><th className="p-2">ID</th><th className="p-2">Market</th><th className="p-2">Side</th><th className="p-2">Price</th><th className="p-2">Size</th><th className="p-2">Status</th></tr>
          </thead>
          <tbody>
            {data.orders.map(o => (
              <tr key={o.order_id} className="border-b border-gray-800">
                <td className="p-2">{o.order_id}</td>
                <td className="p-2">{o.market_ticker}</td>
                <td className="p-2">{o.side}</td>
                <td className="p-2">{o.price_cents}</td>
                <td className="p-2">{o.size}</td>
                <td className="p-2">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="text-gray-400">No orders</p>}
    </div>
  );
}
