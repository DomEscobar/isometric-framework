import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';
export default defineConfig({root:fileURLToPath(new URL('.',import.meta.url)),build:{target:'es2022',outDir:'../../test-results/quellbrunn/build',emptyOutDir:false},server:{host:'127.0.0.1',port:4202,strictPort:true}});
