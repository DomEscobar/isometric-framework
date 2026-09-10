import { defineConfig } from 'vite';

export default defineConfig({ base: './', build: { outDir: 'demo-dist', sourcemap: true,
  rollupOptions: { input: { demo: 'index.html', environments: 'examples/environment-lab/index.html', autotiles: 'examples/autotile-lab/index.html', willowQuay: 'examples/willow-quay/index.html', autumnCrossing: 'examples/autumn-crossing/index.html', mossbell: 'examples/mossbell/index.html', pixelBorough: 'examples/pixel-borough/index.html' } },
} });
