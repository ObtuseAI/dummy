export default function LegacyDashboardDisabled({ version }) {
  return (
    <div className="rounded border border-amber-800 bg-amber-950/30 p-6">
      <h1 className="text-2xl font-bold text-amber-200">Historical stage archive is offline</h1>
      <p className="mt-2 text-sm text-gray-300">
        {version ? `Dashboard V${version} is` : 'Archived dashboards are'} excluded from this
        production build. Use the explicit offline development surface to inspect historical reports.
      </p>
    </div>
  );
}
