import{defineConfig}from'vite';import{fileURLToPath}from'node:url';
export default defineConfig({root:fileURLToPath(new URL('.',import.meta.url)),base:'./',build:{target:'es2022',outDir:'../../test-results/mossbend/one-tree-build',emptyOutDir:false,rollupOptions:{input:fileURLToPath(new URL('./one-tree.html',import.meta.url))}}});
