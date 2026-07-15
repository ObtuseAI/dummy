import { lazy, Suspense } from 'react';

const loaders = import.meta.glob('./V*Dashboard.jsx');
const dashboards = Object.fromEntries(
  Object.entries(loaders).map(([path, loader]) => {
    const match = path.match(/^\.\/V(\d+)Dashboard\.jsx$/);
    return [match?.[1], lazy(loader)];
  }),
);

export default function LegacyDashboardRoute({ version }) {
  const Dashboard = dashboards[String(version)];
  if (!Dashboard) {
    return <div className="p-6 text-red-300">Archived dashboard V{version} is unavailable.</div>;
  }
  return (
    <Suspense fallback={<div className="p-6 text-gray-400">Loading archived dashboard V{version}…</div>}>
      <Dashboard />
    </Suspense>
  );
}
