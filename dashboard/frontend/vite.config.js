import { fileURLToPath, URL } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const archiveEnabled = env.VITE_DUMMY_ARCHIVE_SURFACE === 'offline-dev';
  const archiveModule = archiveEnabled
    ? './src/LegacyDashboardRoute.jsx'
    : './src/LegacyDashboardDisabled.jsx';

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@dummy-archive-route': fileURLToPath(new URL(archiveModule, import.meta.url)),
      },
    },
    server: { port: 5173, proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
  };
});
