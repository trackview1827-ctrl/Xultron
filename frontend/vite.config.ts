import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { serviceWorkerSource } from './src/services/serviceWorkerManifest'

const enableSourceMaps = (globalThis as typeof globalThis & { process?: { env?: Record<string, string | undefined> } }).process?.env?.XULTRON_SOURCEMAPS === 'true'

const injectServiceWorkerManifest: Plugin = {
  name: 'xultron-service-worker-manifest',
  generateBundle(_options, bundle) {
    const buildAssets = Object.keys(bundle).filter(path => path.startsWith('assets/')).sort()
    this.emitFile({ type: 'asset', fileName: 'sw.js', source: serviceWorkerSource(buildAssets) })
  },
}

export default defineConfig({
  plugins: [react(), injectServiceWorkerManifest],
  server: { proxy: { '/api': 'http://127.0.0.1:5000' } },
  build: { target: 'es2022', sourcemap: enableSourceMaps },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    maxWorkers: 2,
    minWorkers: 1,
    coverage: { reporter: ['text', 'html'] },
  },
})
