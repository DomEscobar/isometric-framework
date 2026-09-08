import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

// Own a separate Vite process so tests never depend on a user's dev session.
const url = process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4176';
const owned = !process.env.RUNTIME_QA_URL;
let server;
let startup = '';
try {
  if (owned) {
    server = spawn(process.execPath, [fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url)),
      '--host', '127.0.0.1', '--port', '4176', '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    server.stdout.on('data', data => { startup += data; });
    server.stderr.on('data', data => { startup += data; });
    await new Promise((resolve, reject) => {
      const deadline = setTimeout(() => { clearInterval(poll); reject(new Error(`Vite startup timed out: ${startup}`)); }, 15000);
      const poll = setInterval(() => {
        if (server.exitCode !== null) { clearInterval(poll); clearTimeout(deadline); reject(new Error(startup)); }
        else if (startup.includes('Local:')) { clearInterval(poll); clearTimeout(deadline); resolve(); }
      }, 100);
      server.once('error', error => { clearInterval(poll); clearTimeout(deadline); reject(error); });
    });
  }
  for (const script of ['browser-api', 'levels-browser', 'jump-browser', 'art-browser', 'interactions-browser', 'progress-browser', 'footprint-depth', 'bridge-occlusion']) {
    const result = await new Promise((done, reject) => {
      const test = spawn(process.execPath, [fileURLToPath(new URL(`./${script}.mjs`, import.meta.url))], {
        stdio: 'inherit', windowsHide: true, env: { ...process.env, RUNTIME_QA_URL: url,
          ...(process.env.RUNTIME_QA_OUTPUT ? { RUNTIME_QA_OUTPUT: resolve(process.env.RUNTIME_QA_OUTPUT, script) } : {}),
        },
      });
      test.once('error', reject);
      test.once('exit', code => done(code ?? 1));
    });
    if (result !== 0) process.exitCode = result;
  }
} catch (error) {
  console.error(error);
  process.exitCode = 1;
} finally {
  if (owned && server) server.kill();
}
