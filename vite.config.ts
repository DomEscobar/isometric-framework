import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    lib: { entry: { runtime: 'src/index.ts', core: 'src/core.ts', art: 'src/art.ts' }, formats: ['es'] },
    rollupOptions: { external: ['pixi.js'] },
    sourcemap: true,
  },
});
