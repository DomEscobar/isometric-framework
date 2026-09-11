import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));

export default {
  root,
  base: './',
  server: { watch: { usePolling: true, interval: 300 } },
  build: {
    target: 'esnext',
    outDir: fileURLToPath(new URL('../../test-results/new-village/production', import.meta.url)),
    emptyOutDir: false,
    rollupOptions: { input: fileURLToPath(new URL('./index.html', import.meta.url)) },
  },
};
