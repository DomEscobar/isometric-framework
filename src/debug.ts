import { project } from './geometry.ts';
import type { Cell, DebugSnapshot, RuntimeEvents } from './types.ts';

export interface DebugRuntime {
  getDebugSnapshot(): DebugSnapshot;
  on<K extends 'frame' | 'command' | 'camerachange' | 'viewchange' | 'scenechange' | 'pausechange' | 'destroy'>(
    name: K, listener: (event: RuntimeEvents[K]) => void): () => void;
}
export interface DebugOverlayOptions { container: HTMLElement; panel: HTMLElement }
export interface DebugOverlay { setEnabled(enabled: boolean): void; refresh(): void; destroy(): void }

/** Optional authoring UI. It reads public snapshots and never handles game input. */
export function createDebugOverlay(runtime: DebugRuntime, options: DebugOverlayOptions): DebugOverlay {
  const { container, panel } = options;
  const namespace = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(namespace, 'svg');
  svg.setAttribute('aria-hidden', 'true');
  svg.dataset.runtimeDebug = 'true';
  svg.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:hidden;z-index:2';
  const position = container.style.position;
  const adjustedPosition = getComputedStyle(container).position === 'static';
  if (adjustedPosition) container.style.position = 'relative';
  container.append(svg);
  const label = document.createElement('label');
  label.textContent = 'Inspect entity ';
  const select = document.createElement('select');
  select.setAttribute('aria-label', 'Debug entity');
  label.append(select);
  const text = document.createElement('pre');
  text.dataset.debugDetails = 'true';
  text.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.6 monospace;margin:10px 0';
  const legend = document.createElement('p');
  legend.textContent = 'Cyan: tiles · red: blocking footprint · yellow: route · green: sprite origin/bounds. Footprints show committed occupancy.';
  legend.style.cssText = 'font-size:11px;line-height:1.6';
  panel.append(label, text, legend);
  let enabled = false, disposed = false, elapsed = 0, selected = '', entityKeys = '';
  const disposers: (() => void)[] = [];

  function refresh(): void {
    if (!enabled || disposed) return;
    const snapshot = runtime.getDebugSnapshot();
    const keys = JSON.stringify(snapshot.entities.map(entity => entity.id));
    if (keys !== entityKeys) {
      entityKeys = keys;
      select.replaceChildren(...snapshot.entities.map(entity => new Option(entity.id, entity.id)));
      if (!snapshot.entities.some(entity => entity.id === selected)) selected = snapshot.controlledId ?? snapshot.entities[0]?.id ?? '';
      select.value = selected;
    }
    const entity = snapshot.entities.find(candidate => candidate.id === selected);
    svg.replaceChildren();
    svg.setAttribute('viewBox', `0 0 ${Math.max(1, container.clientWidth)} ${Math.max(1, container.clientHeight)}`);
    const toScreen = (cell: Cell, elevation: number) => {
      const point = project(cell, snapshot.tileWidth, snapshot.tileHeight, elevation);
      return { x: point.x * snapshot.camera.zoom + snapshot.camera.x, y: point.y * snapshot.camera.zoom + snapshot.camera.y };
    };
    const shape = (name: 'polygon' | 'polyline' | 'line' | 'rect' | 'circle' | 'text', attributes: Record<string, number | string>) => {
      const node = document.createElementNS(namespace, name);
      for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
      svg.append(node);
      return node;
    };
    const footprint = (cell: Cell, elevation: number, columns: number, rows: number, color: string, opacity: number) => {
      const points = [
        { c: cell.c - .5, r: cell.r - .5 }, { c: cell.c + columns - .5, r: cell.r - .5 },
        { c: cell.c + columns - .5, r: cell.r + rows - .5 }, { c: cell.c - .5, r: cell.r + rows - .5 },
      ].map(point => toScreen(point, elevation)).map(point => `${point.x},${point.y}`).join(' ');
      shape('polygon', { points, fill: 'none', stroke: color, 'stroke-width': color === '#ef5350' ? 2 : 1, opacity });
    };
    for (const tile of snapshot.tiles) {
      footprint(tile.cell, tile.elevation, 1, 1, '#00bcd4', .32);
      const point = toScreen(tile.cell, tile.elevation);
      if (snapshot.camera.zoom >= .65 && point.x > 0 && point.y > 0 && point.x < container.clientWidth && point.y < container.clientHeight) {
        const node = shape('text', { x: point.x, y: point.y, fill: '#083a42', 'font-size': 9, 'text-anchor': 'middle', 'paint-order': 'stroke', stroke: '#ffffff', 'stroke-width': 2 });
        node.textContent = `${tile.cell.c},${tile.cell.r}`;
      }
    }
    for (const candidate of snapshot.entities) {
      if (candidate.visible && candidate.blocking) footprint(candidate.cell, candidate.elevation, candidate.columns, candidate.rows, '#ef5350', .8);
    }
    if (!entity) { text.textContent = 'No entity to inspect.'; return; }
    const sprite = entity.sprite;
    const pose = entity.pose;
    const origin = toScreen(pose.position, pose.elevation);
    if (entity.visible) {
      if (entity.route.length) {
        const points = [origin, ...entity.route.map(cell => {
          const tile = snapshot.tiles.find(tile => tile.cell.c === cell.c && tile.cell.r === cell.r && tile.cell.level === (cell.level ?? 'ground'));
          return toScreen(cell, tile?.elevation ?? entity.elevation);
        })].map(point => `${point.x},${point.y}`).join(' ');
        shape('polyline', { points, fill: 'none', stroke: '#ffeb3b', 'stroke-width': 3 });
      }
      const anchor = { x: origin.x + (sprite?.offset.x ?? 0) * snapshot.camera.zoom, y: origin.y + (sprite?.offset.y ?? 0) * snapshot.camera.zoom };
      shape('line', { x1: anchor.x - 7, x2: anchor.x + 7, y1: anchor.y, y2: anchor.y, stroke: '#00e676', 'stroke-width': 2 });
      shape('line', { x1: anchor.x, x2: anchor.x, y1: anchor.y - 7, y2: anchor.y + 7, stroke: '#00e676', 'stroke-width': 2 });
      if (sprite) shape('rect', { x: anchor.x - sprite.anchor.x * sprite.width * snapshot.camera.zoom,
        y: anchor.y - sprite.anchor.y * sprite.height * snapshot.camera.zoom,
        width: sprite.width * snapshot.camera.zoom, height: sprite.height * snapshot.camera.zoom,
        fill: 'none', stroke: '#00e676', 'stroke-width': 1, 'stroke-dasharray': '3 2' });
    }
    text.textContent = [
      `${entity.id} (${entity.type})`,
      `Cell: ${entity.cell.c},${entity.cell.r} · ${entity.cell.level} · ${entity.elevation}px`,
      `Pose: ${pose.position.c.toFixed(2)},${pose.position.r.toFixed(2)} · ${pose.elevation.toFixed(1)}px${pose.airborne ? ' · airborne' : ''}`,
      `Footprint: ${entity.columns}×${entity.rows} · body ${entity.bodyHeight}px · ${entity.blocking ? 'blocking' : 'nonblocking'}`,
      `Facing: ${sprite?.facing ?? 'built-in'} · state: ${sprite?.state ?? 'n/a'}`,
      `Clip: ${sprite?.clip ?? 'none'} · frame: ${sprite?.frame ?? 0}`,
      `Texture: ${sprite?.texture ?? 'none'} · override: ${sprite?.override ?? 'none'}`,
      `Anchor: ${sprite ? `${sprite.anchor.x.toFixed(3)},${sprite.anchor.y.toFixed(3)}` : 'n/a'}`,
      `Route: ${entity.route.length ? entity.route.map(cell => `${cell.c},${cell.r}@${cell.level ?? 'ground'}`).join(' → ') : 'none'}`,
      ...(snapshot.tilesTruncated ? ['Grid display capped at 2,000 tiles.'] : []),
    ].join('\n');
  }
  const change = () => { selected = select.value; refresh(); };
  select.addEventListener('change', change);
  disposers.push(runtime.on('frame', ({ deltaSeconds }) => { elapsed += deltaSeconds; if (elapsed >= .1) { elapsed = 0; refresh(); } }));
  for (const event of ['command', 'camerachange', 'viewchange', 'scenechange', 'pausechange'] as const) disposers.push(runtime.on(event, refresh));
  disposers.push(runtime.on('destroy', destroy));
  function destroy(): void {
    if (disposed) return;
    disposed = true;
    disposers.splice(0).forEach(off => off());
    select.removeEventListener('change', change);
    svg.remove(); label.remove(); text.remove(); legend.remove();
    if (adjustedPosition && container.style.position === 'relative') container.style.position = position;
  }
  svg.style.display = 'none';
  panel.hidden = true;
  return { refresh, destroy, setEnabled(value) {
    if (disposed) return;
    enabled = value; svg.style.display = value ? '' : 'none'; panel.hidden = !value;
    if (value) refresh();
  } };
}
