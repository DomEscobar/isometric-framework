import { attachKeyboard, createDpad, createJumpButton, createRuntime, type Scene } from 'isometric-framework';
import './style.css';

const scene: Scene = {
  version: 1, name: 'Neutral calibration room', tileWidth: 72, tileHeight: 36,
  map: [['meadow', 'meadow', 'meadow', 'meadow'], ['meadow', 'meadow', 'meadow', 'meadow'], ['meadow', 'meadow', 'meadow', 'meadow'], ['meadow', 'meadow', 'meadow', 'meadow']],
  tiles: { meadow: { color: 0xa6b99a } },
  entityTypes: {
    player: { visual: { kind: 'actor', color: 0x425b76, height: 32 }, blocking: true },
    stone: { visual: { kind: 'box', color: 0x7c827f, height: 22 }, blocking: true },
    marker: { visual: { kind: 'gem', color: 0xe4ae4a }, blocking: false },
  },
  entities: [{ id: 'hero', type: 'player', c: 0, r: 0 }, { id: 'stone', type: 'stone', c: 1, r: 1 }, { id: 'marker', type: 'marker', c: 3, r: 3 }],
  controlledId: 'hero', diagonal: false,
};

async function bootstrap() {
  const container = document.querySelector<HTMLElement>('#game');
  const status = document.querySelector<HTMLElement>('#status');
  const movementHud = document.querySelector<HTMLElement>('#movement-hud');
  if (!container || !status || !movementHud) throw new Error('Game host is missing');

  const runtime = await createRuntime({ container, scene, input: false, speed: 3, background: 0xf5f0e5 });
  const detachKeyboard = attachKeyboard(runtime, container);
  const dpad = createDpad(runtime, movementHud);
  const jump = createJumpButton(runtime, movementHud);
  runtime.on('arrive', ({ id, cell }) => {
    if (id === 'hero' && cell.c === 3 && cell.r === 3) status.textContent = 'Calibration complete. Define the next rule in PROJECT_CONTRACT.md.';
  });
  runtime.on('error', ({ error }) => { status.textContent = `Runtime error: ${error.message}`; });
  window.addEventListener('beforeunload', () => { detachKeyboard(); dpad.destroy(); jump.destroy(); runtime.destroy(); }, { once: true });
  container.focus({ preventScroll: true });
}

void bootstrap().catch(error => {
  console.error(error);
  const status = document.querySelector<HTMLElement>('#status');
  const detail = error instanceof Error ? error.message : String(error);
  if (status) status.textContent = `Unable to start the calibration: ${detail}`;
});
