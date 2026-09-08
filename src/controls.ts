import type { Point, RuntimeEvents } from './types.ts';

/** Structural contract keeps controls reusable without importing the renderer. */
interface MovementInputTarget {
  readonly isPaused: boolean;
  setMoveInput(direction: Point | null): void;
  jump?(): unknown;
  on<K extends 'inputreset' | 'pausechange' | 'scenechange'>(
    name: K, listener: (event: RuntimeEvents[K]) => void,
  ): () => void;
}

const keyDirections: Readonly<Record<string, Point>> = {
  KeyW: { x: 0, y: -1 }, ArrowUp: { x: 0, y: -1 },
  KeyS: { x: 0, y: 1 }, ArrowDown: { x: 0, y: 1 },
  KeyA: { x: -1, y: 0 }, ArrowLeft: { x: -1, y: 0 },
  KeyD: { x: 1, y: 0 }, ArrowRight: { x: 1, y: 0 },
};

function keyVector(keys: Set<string>): Point | null {
  // Aliases count once. Project grid axes into screen space for the runtime.
  const pressed = (a: string, b: string) => Number(keys.has(a) || keys.has(b));
  const dc = pressed('KeyW', 'ArrowUp') - pressed('KeyS', 'ArrowDown');
  const dr = pressed('KeyD', 'ArrowRight') - pressed('KeyA', 'ArrowLeft');
  const x = dc + dr;
  const y = dr - dc;
  const length = Math.hypot(x, y);
  return length ? { x: x / Math.max(1, length), y: y / Math.max(1, length) } : null;
}

function editable(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(target.closest(
    'input, textarea, select, [contenteditable]:not([contenteditable="false"])',
  ));
}

/** Original grid controls: W northeast, D southeast, S southwest, A northwest. */
export function attachKeyboard(runtime: MovementInputTarget, container: HTMLElement): () => void {
  const doc = container.ownerDocument;
  const win = doc.defaultView!;
  const keys = new Set<string>();
  const originalTabIndex = container.getAttribute('tabindex');
  if (originalTabIndex === null) container.tabIndex = 0;
  let destroyed = false;

  const clear = () => {
    if (keys.size === 0) return;
    keys.clear();
    runtime.setMoveInput(null);
  };
  const keydown = (event: KeyboardEvent) => {
    if ((!keyDirections[event.code] && !(event.code === 'Space' && runtime.jump)) || runtime.isPaused || editable(event.target)
      || event.ctrlKey || event.metaKey || event.altKey || !container.contains(doc.activeElement)) return;
    event.preventDefault();
    if (event.code === 'Space') {
      if (!event.repeat) runtime.jump?.();
      return;
    }
    if (event.repeat || keys.has(event.code)) return;
    keys.add(event.code);
    runtime.setMoveInput(keyVector(keys));
  };
  const keyup = (event: KeyboardEvent) => {
    if (!keys.delete(event.code)) return;
    runtime.setMoveInput(keyVector(keys));
  };
  const focusout = (event: FocusEvent) => {
    if (!(event.relatedTarget instanceof Node) || !container.contains(event.relatedTarget)
      || editable(event.relatedTarget)) clear();
  };
  const visibility = () => { if (doc.hidden) clear(); };
  container.addEventListener('keydown', keydown);
  container.addEventListener('focusout', focusout);
  win.addEventListener('keyup', keyup);
  win.addEventListener('blur', clear);
  doc.addEventListener('visibilitychange', visibility);
  const unsubscribe = [
    runtime.on('inputreset', clear), runtime.on('scenechange', clear),
    runtime.on('pausechange', clear),
  ];

  return () => {
    if (destroyed) return;
    destroyed = true;
    container.removeEventListener('keydown', keydown);
    container.removeEventListener('focusout', focusout);
    win.removeEventListener('keyup', keyup);
    win.removeEventListener('blur', clear);
    doc.removeEventListener('visibilitychange', visibility);
    unsubscribe.forEach(off => off());
    if (originalTabIndex === null && container.getAttribute('tabindex') === '0') container.removeAttribute('tabindex');
    // Disposal is also supported after the owning runtime has been destroyed.
    try { clear(); } catch { keys.clear(); }
  };
}

/** Mount a four-button grid movement HUD. The supplied container should be positioned. */
export function createDpad(runtime: MovementInputTarget, container: HTMLElement): {
  element: HTMLElement; destroy(): void;
} {
  const doc = container.ownerDocument;
  const win = doc.defaultView!;
  const element = doc.createElement('div');
  element.className = 'runtime-dpad';
  element.setAttribute('role', 'group');
  element.setAttribute('aria-label', 'Movement controls');
  element.setAttribute('aria-description', 'Hold the buttons or use WASD and arrow keys to move along the map grid.');
  element.style.cssText = 'position:absolute;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));width:132px;height:132px;display:grid;grid-template:repeat(3,44px)/repeat(3,44px);touch-action:none;user-select:none;-webkit-user-select:none;z-index:10;';
  const directions = [
    { code: 'KeyW', alias: 'ArrowUp', text: 'W ↗', label: 'Move northeast (W)', row: 1, column: 2 },
    { code: 'KeyD', alias: 'ArrowRight', text: 'D ↘', label: 'Move southeast (D)', row: 2, column: 3 },
    { code: 'KeyS', alias: 'ArrowDown', text: 'S ↙', label: 'Move southwest (S)', row: 3, column: 2 },
    { code: 'KeyA', alias: 'ArrowLeft', text: 'A ↖', label: 'Move northwest (A)', row: 2, column: 1 },
  ];
  const buttons = directions.map(direction => {
    const button = doc.createElement('button');
    button.type = 'button';
    button.className = `runtime-dpad-button runtime-dpad-${direction.code.slice(-1).toLowerCase()}`;
    button.dataset.key = direction.code;
    button.textContent = direction.text;
    button.setAttribute('aria-label', direction.label);
    button.setAttribute('aria-keyshortcuts', `${direction.code.slice(-1)} ${direction.alias}`);
    button.setAttribute('aria-pressed', 'false');
    button.style.cssText = `grid-row:${direction.row};grid-column:${direction.column};width:44px;height:44px;padding:0;border:0;border-radius:14px;background:#f5f2e6;color:#475a3e;font:600 12px/1 system-ui,sans-serif;box-shadow:0 3px 12px rgba(37,53,40,.12);touch-action:none;user-select:none;-webkit-user-select:none;cursor:pointer;transition:background .12s,color .12s,transform .12s;`;
    element.appendChild(button);
    return button;
  });
  container.appendChild(element);
  const pointers = new Map<number, { button: HTMLButtonElement; code: string }>();
  const keys = new Map<string, string>();
  let engaged = false;
  let destroyed = false;

  const sync = () => {
    const held = new Set([...keys.values(), ...Array.from(pointers.values(), pointer => pointer.code)]);
    buttons.forEach((button, index) => {
      const direction = directions[index]!;
      const pressed = held.has(direction.code) || held.has(direction.alias);
      button.setAttribute('aria-pressed', String(pressed));
      button.setAttribute('aria-disabled', String(runtime.isPaused));
      button.style.background = pressed ? '#667f57' : '#f5f2e6';
      button.style.color = pressed ? '#fff' : '#475a3e';
      button.style.transform = pressed ? 'scale(.94)' : 'scale(1)';
      button.style.cursor = runtime.isPaused ? 'default' : 'pointer';
    });
    element.setAttribute('aria-disabled', String(runtime.isPaused));
    element.style.opacity = runtime.isPaused ? '.45' : '1';
    const wasEngaged = engaged;
    engaged = held.size > 0;
    if (engaged || wasEngaged) runtime.setMoveInput(runtime.isPaused ? null : keyVector(held));
  };
  const reset = () => {
    const captures = [...pointers.entries()];
    pointers.clear();
    keys.clear();
    for (const [pointerId, { button }] of captures) {
      if (button.hasPointerCapture(pointerId)) button.releasePointerCapture(pointerId);
    }
    sync();
  };
  const consume = (event: Event) => { event.preventDefault(); event.stopPropagation(); };
  const buttonFor = (target: EventTarget | null): HTMLButtonElement | undefined => {
    if (!(target instanceof Element)) return undefined;
    return buttons.find(button => button === target || button.contains(target));
  };
  const pointerdown = (event: PointerEvent) => {
    consume(event);
    const button = buttonFor(event.target);
    if (!button || runtime.isPaused || event.button !== 0 || pointers.has(event.pointerId)) return;
    button.focus({ preventScroll: true });
    button.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { button, code: button.dataset.key! });
    sync();
  };
  const pointerend = (event: PointerEvent) => {
    consume(event);
    const pointer = pointers.get(event.pointerId);
    if (!pointer) return;
    pointers.delete(event.pointerId);
    if (pointer.button.hasPointerCapture(event.pointerId)) pointer.button.releasePointerCapture(event.pointerId);
    sync();
  };
  const keydown = (event: KeyboardEvent) => {
    if (event.code === 'Space' && runtime.jump) {
      event.stopPropagation();
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      event.preventDefault();
      if (!runtime.isPaused && !event.repeat) runtime.jump();
      return;
    }
    const activation = event.code === 'Space' || event.code === 'Enter';
    const button = buttonFor(event.target);
    const code = activation ? button?.dataset.key : keyDirections[event.code] ? event.code : undefined;
    if (!code) return;
    event.stopPropagation();
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    if (runtime.isPaused || event.repeat || keys.has(event.code)) return;
    keys.set(event.code, code);
    sync();
  };
  const keyup = (event: KeyboardEvent) => {
    if (!keys.delete(event.code)) return;
    if (event.code === 'Space' || event.code === 'Enter') event.preventDefault();
    sync();
  };
  const focusout = (event: FocusEvent) => {
    if (!(event.relatedTarget instanceof Node) || !element.contains(event.relatedTarget)) reset();
  };
  const visibility = () => { if (doc.hidden) reset(); };
  element.addEventListener('pointerdown', pointerdown);
  element.addEventListener('pointermove', consume);
  element.addEventListener('pointerup', pointerend);
  element.addEventListener('pointercancel', pointerend);
  element.addEventListener('lostpointercapture', pointerend);
  element.addEventListener('click', consume);
  element.addEventListener('contextmenu', consume);
  element.addEventListener('keydown', keydown);
  element.addEventListener('focusout', focusout);
  win.addEventListener('keyup', keyup);
  win.addEventListener('blur', reset);
  doc.addEventListener('visibilitychange', visibility);
  const unsubscribe = [runtime.on('inputreset', reset), runtime.on('scenechange', reset), runtime.on('pausechange', reset)];
  sync();
  return {
    element,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      unsubscribe.forEach(off => off());
      element.removeEventListener('pointerdown', pointerdown);
      element.removeEventListener('pointermove', consume);
      element.removeEventListener('pointerup', pointerend);
      element.removeEventListener('pointercancel', pointerend);
      element.removeEventListener('lostpointercapture', pointerend);
      element.removeEventListener('click', consume);
      element.removeEventListener('contextmenu', consume);
      element.removeEventListener('keydown', keydown);
      element.removeEventListener('focusout', focusout);
      win.removeEventListener('keyup', keyup);
      win.removeEventListener('blur', reset);
      doc.removeEventListener('visibilitychange', visibility);
      try { reset(); } catch { /* The runtime may already be destroyed. */ }
      element.remove();
    },
  };
}

/** A jump action that preserves focus and any movement held on a separate HUD. */
export function createJumpButton(runtime: MovementInputTarget, container: HTMLElement): {
  element: HTMLElement; destroy(): void;
} {
  const doc = container.ownerDocument;
  const win = doc.defaultView!;
  const element = doc.createElement('button');
  element.type = 'button';
  element.className = 'runtime-jump-button';
  element.textContent = 'Jump';
  element.setAttribute('aria-label', 'Jump');
  element.setAttribute('aria-keyshortcuts', 'Space Enter');
  element.style.cssText = 'position:absolute;right:max(164px,calc(env(safe-area-inset-right) + 148px));bottom:max(50px,calc(env(safe-area-inset-bottom) + 34px));width:64px;height:64px;border:0;border-radius:50%;background:#667f57;color:#fff;font:600 13px/1 system-ui,sans-serif;box-shadow:0 3px 12px rgba(37,53,40,.12);touch-action:none;user-select:none;-webkit-user-select:none;cursor:pointer;z-index:10;transition:background .12s,transform .12s;';
  container.appendChild(element);
  let pointerId: number | null = null;
  let heldKey: string | null = null;
  let destroyed = false;
  const available = () => !runtime.isPaused && Boolean(runtime.jump);
  const refresh = () => {
    const pressed = pointerId !== null || heldKey !== null;
    element.setAttribute('aria-disabled', String(!available()));
    element.style.opacity = available() ? '1' : '.45';
    element.style.transform = pressed ? 'scale(.94)' : 'scale(1)';
    element.style.background = pressed ? '#475f39' : '#667f57';
    element.style.cursor = available() ? 'pointer' : 'default';
  };
  const reset = () => {
    const previousPointer = pointerId;
    pointerId = null;
    heldKey = null;
    if (previousPointer !== null && element.hasPointerCapture(previousPointer)) element.releasePointerCapture(previousPointer);
    refresh();
  };
  const consume = (event: Event) => { event.preventDefault(); event.stopPropagation(); };
  const pointerdown = (event: PointerEvent) => {
    // Preventing the native focus transfer is essential for two-finger movement + jump.
    consume(event);
    if (!available() || event.button !== 0 || pointerId !== null || heldKey !== null) return;
    pointerId = event.pointerId;
    element.setPointerCapture(event.pointerId);
    refresh();
    runtime.jump?.();
  };
  const pointerend = (event: PointerEvent) => {
    consume(event);
    if (event.pointerId === pointerId) reset();
  };
  const keydown = (event: KeyboardEvent) => {
    if (event.code !== 'Space' && event.code !== 'Enter') return;
    event.stopPropagation();
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    if (!available() || event.repeat || heldKey !== null || pointerId !== null) return;
    heldKey = event.code;
    refresh();
    runtime.jump?.();
  };
  const keyup = (event: KeyboardEvent) => {
    if (event.code !== heldKey) return;
    event.preventDefault();
    heldKey = null;
    refresh();
  };
  const click = (event: MouseEvent) => {
    consume(event);
    // Pointer activation already fired on press. Detail-zero clicks support assistive tools.
    if (event.detail === 0 && pointerId === null && heldKey === null && available()) runtime.jump?.();
  };
  const focusout = () => { if (pointerId === null) reset(); };
  const visibility = () => { if (doc.hidden) reset(); };
  element.addEventListener('pointerdown', pointerdown);
  element.addEventListener('pointermove', consume);
  element.addEventListener('pointerup', pointerend);
  element.addEventListener('pointercancel', pointerend);
  element.addEventListener('lostpointercapture', pointerend);
  element.addEventListener('click', click);
  element.addEventListener('contextmenu', consume);
  element.addEventListener('keydown', keydown);
  element.addEventListener('focusout', focusout);
  win.addEventListener('keyup', keyup);
  win.addEventListener('blur', reset);
  doc.addEventListener('visibilitychange', visibility);
  const unsubscribe = [runtime.on('inputreset', reset), runtime.on('scenechange', reset), runtime.on('pausechange', reset)];
  refresh();
  return {
    element,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      unsubscribe.forEach(off => off());
      element.removeEventListener('pointerdown', pointerdown);
      element.removeEventListener('pointermove', consume);
      element.removeEventListener('pointerup', pointerend);
      element.removeEventListener('pointercancel', pointerend);
      element.removeEventListener('lostpointercapture', pointerend);
      element.removeEventListener('click', click);
      element.removeEventListener('contextmenu', consume);
      element.removeEventListener('keydown', keydown);
      element.removeEventListener('focusout', focusout);
      win.removeEventListener('keyup', keyup);
      win.removeEventListener('blur', reset);
      doc.removeEventListener('visibilitychange', visibility);
      reset();
      element.remove();
    },
  };
}

/** Mount a visible HUD stick. The supplied container should be positioned. */
export function createJoystick(runtime: MovementInputTarget, container: HTMLElement): {
  element: HTMLElement; destroy(): void;
} {
  const doc = container.ownerDocument;
  const win = doc.defaultView!;
  const element = doc.createElement('div');
  const knob = doc.createElement('div');
  const label = doc.createElement('span');
  element.className = 'runtime-stick';
  element.tabIndex = 0;
  element.setAttribute('role', 'group');
  element.setAttribute('aria-label', 'Movement stick');
  element.setAttribute('aria-description', 'Drag to walk. When focused, use WASD or arrow keys.');
  element.style.cssText = 'position:absolute;left:max(20px,env(safe-area-inset-left));bottom:max(22px,env(safe-area-inset-bottom));width:112px;height:112px;border-radius:50%;background:rgba(245,242,230,.88);box-shadow:0 5px 28px rgba(37,53,40,.13),inset 0 0 0 1px rgba(85,105,76,.10);touch-action:none;user-select:none;-webkit-user-select:none;z-index:10;cursor:grab;display:grid;place-items:center;';
  knob.className = 'runtime-stick-knob';
  knob.setAttribute('aria-hidden', 'true');
  knob.style.cssText = 'width:44px;height:44px;border-radius:50%;background:#667f57;box-shadow:0 3px 8px rgba(39,61,29,.22);pointer-events:none;transform:translate(0px,0px);';
  label.textContent = 'MOVE';
  label.setAttribute('aria-hidden', 'true');
  label.style.cssText = 'position:absolute;bottom:9px;font:600 9px/1 system-ui,sans-serif;letter-spacing:1.5px;color:#53654a;pointer-events:none;';
  element.append(knob, label);
  container.appendChild(element);
  const keys = new Set<string>();
  let pointerId: number | null = null;
  let engaged = false;
  let destroyed = false;
  const maxThrow = 32;
  const deadZone = 0.18;

  const disabled = () => {
    element.setAttribute('aria-disabled', String(runtime.isPaused));
    element.style.opacity = runtime.isPaused ? '.45' : '1';
    element.style.cursor = runtime.isPaused ? 'default' : pointerId === null ? 'grab' : 'grabbing';
  };
  const reset = () => {
    const previousPointer = pointerId;
    pointerId = null;
    keys.clear();
    knob.style.transform = 'translate(0px,0px)';
    if (previousPointer !== null && element.hasPointerCapture(previousPointer)) element.releasePointerCapture(previousPointer);
    if (engaged) {
      engaged = false;
      runtime.setMoveInput(null);
    }
    disabled();
  };
  const updatePointer = (event: PointerEvent) => {
    const rect = element.getBoundingClientRect();
    const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2);
    const distance = Math.hypot(dx, dy);
    const clamped = Math.min(distance, maxThrow);
    const x = distance ? dx / distance : 0;
    const y = distance ? dy / distance : 0;
    knob.style.transform = `translate(${x * clamped}px,${y * clamped}px)`;
    const strength = Math.max(0, (clamped / maxThrow - deadZone) / (1 - deadZone));
    engaged = true;
    runtime.setMoveInput(strength ? { x: x * strength, y: y * strength } : null);
  };
  const consume = (event: Event) => { event.preventDefault(); event.stopPropagation(); };
  const pointerdown = (event: PointerEvent) => {
    consume(event);
    if (runtime.isPaused || pointerId !== null || event.button !== 0) return;
    reset();
    pointerId = event.pointerId;
    element.focus({ preventScroll: true });
    element.setPointerCapture(event.pointerId);
    disabled();
    updatePointer(event);
  };
  const pointermove = (event: PointerEvent) => {
    consume(event);
    if (event.pointerId !== pointerId) return;
    if (runtime.isPaused) { reset(); return; }
    updatePointer(event);
  };
  const pointerend = (event: PointerEvent) => {
    consume(event);
    if (event.pointerId === pointerId) reset();
  };
  const keydown = (event: KeyboardEvent) => {
    if (!keyDirections[event.code]) return;
    event.stopPropagation();
    if (runtime.isPaused || event.ctrlKey || event.metaKey || event.altKey || pointerId !== null) return;
    event.preventDefault();
    if (event.repeat || keys.has(event.code)) return;
    keys.add(event.code);
    engaged = true;
    const vector = keyVector(keys);
    knob.style.transform = `translate(${(vector?.x ?? 0) * maxThrow}px,${(vector?.y ?? 0) * maxThrow}px)`;
    runtime.setMoveInput(vector);
  };
  const keyup = (event: KeyboardEvent) => {
    if (!keys.delete(event.code)) return;
    const vector = keyVector(keys);
    knob.style.transform = `translate(${(vector?.x ?? 0) * maxThrow}px,${(vector?.y ?? 0) * maxThrow}px)`;
    runtime.setMoveInput(vector);
    engaged = keys.size > 0;
  };
  const focusout = () => { if (pointerId === null) reset(); };
  const visibility = () => { if (doc.hidden) reset(); };
  element.addEventListener('pointerdown', pointerdown);
  element.addEventListener('pointermove', pointermove);
  element.addEventListener('pointerup', pointerend);
  element.addEventListener('pointercancel', pointerend);
  element.addEventListener('lostpointercapture', pointerend);
  element.addEventListener('click', consume);
  element.addEventListener('contextmenu', consume);
  element.addEventListener('keydown', keydown);
  element.addEventListener('focusout', focusout);
  win.addEventListener('keyup', keyup);
  win.addEventListener('blur', reset);
  doc.addEventListener('visibilitychange', visibility);
  const unsubscribe = [runtime.on('inputreset', reset), runtime.on('scenechange', reset), runtime.on('pausechange', reset)];
  disabled();
  return {
    element,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      unsubscribe.forEach(off => off());
      element.removeEventListener('pointerdown', pointerdown);
      element.removeEventListener('pointermove', pointermove);
      element.removeEventListener('pointerup', pointerend);
      element.removeEventListener('pointercancel', pointerend);
      element.removeEventListener('lostpointercapture', pointerend);
      element.removeEventListener('click', consume);
      element.removeEventListener('contextmenu', consume);
      element.removeEventListener('keydown', keydown);
      element.removeEventListener('focusout', focusout);
      win.removeEventListener('keyup', keyup);
      win.removeEventListener('blur', reset);
      doc.removeEventListener('visibilitychange', visibility);
      try { reset(); } catch { /* The runtime may already be destroyed. */ }
      element.remove();
    },
  };
}
