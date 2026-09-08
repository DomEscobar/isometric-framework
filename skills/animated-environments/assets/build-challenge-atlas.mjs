/** Deterministic, hand-authored geometry for skill calibration, not production art. */
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const frames = {};
const groups = [];
const polygon = (points, fill, extra = '') => `<polygon points="${points}" fill="${fill}" ${extra}/>`;
const line = (x1, y1, x2, y2, stroke, width = 2) => `<path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${stroke}" stroke-width="${width}"/>`;
function add(id, x, y, width, height, root, footprint, content, note) {
  frames[id] = { image: 'challenge', frame: { x, y, width, height }, rootPixel: { x: root[0], y: root[1] }, anchor: { x: root[0] / width, y: root[1] / height }, footprint, note };
  groups.push(`<g id="${id}" transform="translate(${x} ${y})">${content}</g>`);
}

for (let phase = 0; phase < 4; phase++) {
  const ripple = [];
  for (let row = 0; row < 4; row++) {
    for (let repeat = -1; repeat < 5; repeat++) {
      const x = repeat * 16 + phase * 4 + (row % 2) * 8;
      ripple.push(line(x, 6 + row * 6, x + 6, 6 + row * 6, row % 2 ? '#55b9ad' : '#3b9b99'));
    }
  }
  add(`river-${phase}`, phase * 64, 0, 64, 32, [32, 16], { columns: 1, rows: 1 },
    `<defs><clipPath id="river-inset-${phase}">${polygon('6,16 32,3 58,16 32,29', '#fff')}</clipPath></defs>` +
    polygon('0,16 32,0 64,16 32,32', '#267e80') +
    `<g clip-path="url(#river-inset-${phase})">${ripple.join('')}</g>`,
    'Exact 64x32 diamond. The unchanged perimeter meets neighboring cells; interior ripple phase advances 4 pixels modulo a 16-pixel period. Four-frame seamless temporal loop.');
}

// All stone strings are shared verbatim across frames: no basin/column animation drift.
const basinBack = polygon('16,148 112,100 208,148 112,196', '#e4bd7c') +
  polygon('16,148 112,196 112,208 16,160', '#af744b') +
  polygon('112,196 208,148 208,160 112,208', '#87523c') +
  polygon('32,148 112,108 192,148 112,188', '#266f73');
const column = polygon('104,143 112,139 120,143 112,147', '#f2d59a') +
  polygon('104,99 112,103 112,147 104,143', '#bb8856') +
  polygon('112,103 120,99 120,143 112,147', '#926040') +
  polygon('104,99 112,95 120,99 112,103', '#f7d99d') +
  polygon('88,93 112,81 136,93 112,105', '#b3794d') +
  polygon('88,88 112,76 136,88 112,100', '#e8c387') +
  polygon('94,88 112,79 130,88 112,97', '#358e8a') +
  polygon('108,76 112,74 116,76 112,78', '#f9dd9f') +
  polygon('108,76 112,78 112,88 108,86', '#bc8651') +
  polygon('112,78 116,76 116,86 112,88', '#8a5738');
const basinFront = polygon('16,148 24,144 112,188 112,196', '#efd098') +
  polygon('112,188 200,144 208,148 112,196', '#cc9a63') +
  line(40,160,40,169,'#8e5d3f') + line(64,172,64,181,'#8e5d3f') +
  line(88,184,88,193,'#8e5d3f') + line(136,184,136,193,'#6c4334') +
  line(160,172,160,181,'#6c4334') + line(184,160,184,169,'#6c4334');
for (let phase = 0; phase < 4; phase++) {
  const pulse = [0, 2, 0, -2][phase];
  const water = `<g fill="none" stroke="#87d6bd" stroke-width="2">` +
    `<path d="M112 82Q${92 + pulse} 66 74 142M112 82Q${134 - pulse} 66 150 142"/>` +
    `<path d="M100 94Q83 105 ${80 + pulse} 153M124 94Q142 105 ${144 - pulse} 153"/>` +
    `<path d="M${64 - pulse} 145l12 -6 12 6 -12 6Z M${138 + pulse} 145l12 -6 12 6 -12 6Z"/>` +
    `<path d="M96 ${169 + pulse}l16 -8 16 8 -16 8Z"/></g>`;
  add(`fountain-${phase}`, phase * 256, 32, 256, 224, [48, 160], { columns: 3, rows: 3 },
    basinBack + water + column + basinFront,
    'Fixed 3x3 stone basin ground corners (16,160),(112,112),(208,160),(112,208); first occupied tile center/root (48,160). Basin wall rises 12px. Decorative center reaches y74; choose collision body height explicitly, independently of this silhouette. Only water paths vary; stone and anchor are identical in every frame.');
}

add('deck', 0, 272, 64, 32, [32, 16], { columns: 1, rows: 1 },
  polygon('0,16 32,0 64,16 32,32', '#c7a270') +
  polygon('2,16 32,1 62,16 32,31', '#d8b782') +
  line(16,8,48,24,'#b69165',1) + line(16,24,48,8,'#b69165',1),
  'Flat walking surface; visual texture only. Deck walkability and absolute height are supplied by floor data.');

add('pier', 80, 272, 64, 104, [32, 88], { columns: 1, rows: 1 },
  polygon('0,88 32,72 64,88 32,104', '#8e674f') +
  polygon('4,18 32,32 32,102 4,88', '#b08761') +
  polygon('32,32 60,18 60,88 32,102', '#805e49') +
  polygon('0,16 32,0 64,16 32,32', '#e1c291') +
  line(4,40,32,54,'#8d654b') + line(4,64,32,78,'#8d654b') +
  line(32,54,60,40,'#624638') + line(32,78,60,64,'#624638'),
  'One-cell ground support with a 72px vertical rise from root (32,88) to top center (32,16). Ground occupancy belongs on ground; do not block the deck floor with this entity.');

add('rail-c', 160, 272, 64, 64, [32, 48], { columns: 1, rows: 1 },
  polygon('0,24 28,10 28,34 0,48', '#bd9569') +
  polygon('28,10 32,12 32,36 28,34', '#8f674c') +
  polygon('0,24 28,10 32,12 4,26', '#f0d6a2') +
  line(9,27,9,42,'#8e684e',3) + line(21,21,21,36,'#8e684e',3),
  'Thin 24px-high stone rail along the c-axis, at the tile boundary from local (-32,0) to (0,-16). Full-cell blocking is deliberately conservative; use a dedicated nonwalkable rail row, never a walkable lane.');

add('rail-r', 240, 272, 64, 64, [32, 48], { columns: 1, rows: 1 },
  polygon('32,8 60,22 60,46 32,32', '#ae805b') +
  polygon('28,10 32,8 32,32 28,34', '#d2ab78') +
  polygon('28,10 32,8 64,24 60,26', '#f0d6a2') +
  line(41,17,41,36,'#805940',3) + line(53,23,53,42,'#805940',3),
  'Thin 24px-high stone rail along the r-axis on the far boundary from local (0,-16) to (32,0). Use only with explicit dedicated blocker cells.');

add('proxy', 320, 272, 1, 1, [0, 0], { columns: 1, rows: 1 }, '',
  'Fully transparent semantic/collision proxy. No rendered outline; inspect occupancy in the debug overlay.');

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="384" viewBox="0 0 1024 384" shape-rendering="crispEdges"><title>Animated environment workflow calibration atlas</title><desc>Deterministically authored sandstone and teal geometry; functional fixture, not production reference artwork.</desc>${groups.join('\n')}</svg>\n`;
const source = {
  schemaVersion: 1,
  image: 'challenge',
  source: 'challenge-atlas.svg',
  generator: 'build-challenge-atlas.mjs',
  provenance: { method: 'Deterministically authored SVG geometry', purpose: 'Neutral shared fixture for comparing skill workflows', productionArt: false, referenceImagesReproduced: false, externalAssets: false },
  atlas: { width: 1024, height: 384 },
  tile: { width: 64, height: 32, units: 'world pixels at scale 1', projection: 'x=(c+r)*32; y=(r-c)*16-elevation' },
  animation: { river: { frames: ['river-0','river-1','river-2','river-3'], fps: 4, loop: true }, fountain: { frames: ['fountain-0','fountain-1','fountain-2','fountain-3'], fps: 4, loop: true } },
  notes: [
    'Frame anchors are measured from each frame canvas, not the atlas origin. Use width equal to source frame width at scale 1.',
    'Footprint metadata is an authored intent and still requires overlay + gameplay review. Frame alpha never determines collision.',
    'SVG has transparent exterior pixels and no background removal requirement. It is a functional workflow probe, not evidence that generated illustration will satisfy the same bounds.',
    'The fountain is a monolithic visual for a fully blocked basin; the bridge intentionally has separate deck, ground support, and rail pieces. No bridge arch is implied by the pier texture.'
  ],
  frames,
};
writeFileSync(join(here, 'challenge-atlas.svg'), svg);
writeFileSync(join(here, 'challenge-sources.json'), JSON.stringify(source, null, 2) + '\n');
console.log(`Wrote ${Object.keys(frames).length} frames to challenge-atlas.svg and challenge-sources.json`);
