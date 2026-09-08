import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { autotileMasks } from '../../../src/core.ts';

// Authoring only: generated material RGB projected onto fixed tile geometry.
// Run from any directory: node --experimental-strip-types path/to/prepare-ground.mjs
// The source sheet is retained unchanged; these are assembled materials, not
// independently generated finished tiles or hand-painted replacement textures.
const sourceURL = new URL('../../autotile-lab/art/material-source.png', import.meta.url);
const outputURL = new URL('./', import.meta.url);
const source = await readFile(sourceURL);
const masks = [...autotileMasks('blob47')];
const recipe = {
  tileWidth: 64, tileHeight: 32, materialResolution: 32,
  alphaMode: 'opaque-material-rgb',
  crops: { soil: [16, 16, 590, 590], paving: [644, 16, 590, 590], wall: [16, 644, 590, 590], grass: [644, 644, 590, 590] },
  // Apply one subtle global material grade to each swatch, never painted pixels.
  grade: {
    grass: { saturation: 0.68, multiply: [0.97, 1.03, 1.09] },
    paving: { saturation: 0.68, multiply: [0.98, 1, 1.03] },
    wall: { saturation: 0.68, multiply: [0.98, 1, 1.03] },
    soil: { saturation: 0.78, multiply: [1, 1, 1] },
  },
  exposedMargin: 0.115, marginVariation: 0.018, soilLip: 0.024,
  structures: [
    { id: 'parapet-left', c: [-0.5, -0.25], r: [-0.5, 0.5], height: 24, face: 'c-min' },
    { id: 'parapet-right', c: [0.25, 0.5], r: [-0.5, 0.5], height: 24, face: 'c-min' },
    { id: 'quay-wall', c: [-0.5, 0.5], r: [0.375, 0.5], height: 16, face: 'r-max' },
  ],
};
const browser = await chromium.launch();
let result;
try {
  const page = await browser.newPage();
  result = await page.evaluate(async ({ encoded, masks, recipe }) => {
    const image = new Image();
    image.src = `data:image/png;base64,${encoded}`;
    await image.decode();
    const source = document.createElement('canvas');
    source.width = image.width; source.height = image.height;
    const sourceContext = source.getContext('2d');
    sourceContext.drawImage(image, 0, 0);
    const original = sourceContext.getImageData(0, 0, image.width, image.height).data;
    const materials = {};
    const resolution = recipe.materialResolution;
    for (const [name, rect] of Object.entries(recipe.crops)) {
      const [x, y, width, height] = rect;
      if (x < 0 || y < 0 || x + width > image.width || y + height > image.height) throw new Error(`Crop outside source: ${name}`);
      for (let sy = y; sy < y + height; sy++) for (let sx = x; sx < x + width; sx++) {
        if (original[(sy * image.width + sx) * 4 + 3] < 200) throw new Error(`Material ${name} contains cutout alpha; opaque normalization is not appropriate`);
      }
      const swatch = document.createElement('canvas');
      swatch.width = swatch.height = resolution;
      const context = swatch.getContext('2d');
      context.imageSmoothingEnabled = true; context.imageSmoothingQuality = 'high';
      context.drawImage(image, x, y, width, height, 0, 0, resolution, resolution);
      materials[name] = context.getImageData(0, 0, resolution, resolution).data;
    }
    const mirror = value => {
      const p = ((value % 1) + 1) % 1;
      return p < 0.5 ? p * 2 : (1 - p) * 2;
    };
    const sample = (name, c, r) => {
      const x = Math.round(mirror(c + 0.5) * (resolution - 1));
      const y = Math.round(mirror(r + 0.5) * (resolution - 1));
      const index = (y * resolution + x) * 4, pixels = materials[name];
      const gray = pixels[index] * 0.2126 + pixels[index + 1] * 0.7152 + pixels[index + 2] * 0.0722;
      const grade = recipe.grade[name];
      return [0, 1, 2].map(channel => Math.max(0, Math.min(255, Math.round(
        (gray + (pixels[index + channel] - gray) * grade.saturation) * grade.multiply[channel],
      )))).concat(255);
    };
    const width = recipe.tileWidth, height = recipe.tileHeight, columns = 8;
    const ids = [...masks.map(mask => `path-${mask}`), 'grass', 'paved'];
    const atlas = document.createElement('canvas');
    const groundHeight = Math.ceil(ids.length / columns) * height;
    atlas.width = columns * width; atlas.height = groundHeight + 80;
    const context = atlas.getContext('2d');
    const pixels = context.createImageData(atlas.width, atlas.height);
    const textures = {}, variants = {}, counts = [], signatures = [];
    // Variation shares the same local boundary endpoints for every tile. It moves
    // only the material transition; it never changes the diamond or collisions.
    const margin = tangent => recipe.exposedMargin + recipe.marginVariation * (Math.cos(tangent * Math.PI * 4) - 1);
    for (let frame = 0; frame < ids.length; frame++) {
      const id = ids[frame], mask = masks[frame] ?? 255;
      const ox = frame % columns * width, oy = Math.floor(frame / columns) * height;
      let visible = 0, signature = 2166136261;
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const dx = x + 0.5 - width / 2, dy = y + 0.5 - height / 2;
        const c = dx / width - dy / height, r = dx / width + dy / height;
        if (c < -0.5 || c >= 0.5 || r < -0.5 || r >= 0.5) continue;
        let material = id === 'grass' ? 'grass' : 'paving';
        if (frame < masks.length) {
          let distance = Infinity;
          if (!(mask & 1)) distance = Math.min(distance, c + 0.5 - margin(r));
          if (!(mask & 2)) distance = Math.min(distance, 0.5 - c - margin(r));
          if (!(mask & 4)) distance = Math.min(distance, r + 0.5 - margin(c));
          if (!(mask & 8)) distance = Math.min(distance, 0.5 - r - margin(c));
          for (const [dc, dr, bit, sides] of [[-1, -1, 16, 5], [1, -1, 32, 6], [-1, 1, 64, 9], [1, 1, 128, 10]]) {
            if (!(mask & bit) && (mask & sides) === sides) {
              distance = Math.min(distance, Math.hypot(c - dc * 0.5, r - dr * 0.5) - recipe.exposedMargin);
            }
          }
          material = distance < -recipe.soilLip ? 'grass' : distance < 0 ? 'soil' : 'paving';
        }
        const rgba = sample(material, c, r);
        pixels.data.set(rgba, ((oy + y) * atlas.width + ox + x) * 4);
        visible++;
        for (const value of rgba) signature = Math.imul(signature ^ value, 16777619) >>> 0;
      }
      textures[id] = { image: 'ground', frame: { x: ox, y: oy, width, height }, anchor: { x: 0.5, y: 0.5 } };
      if (frame < masks.length) variants[mask] = id;
      counts.push({ id, visible }); signatures.push({ id, signature });
    }
    const structureCoverage = [];
    for (let index = 0; index < recipe.structures.length; index++) {
      const structure = recipe.structures[index];
      const ox = index * 80, oy = groundHeight, rootX = 40, rootY = 56;
      let visible = 0;
      for (let py = 0; py < 80; py++) for (let px = 0; px < 80; px++) {
        const x = px + 0.5 - rootX, y = py + 0.5 - rootY;
        const c = x / width - (y + structure.height) / height;
        const r = x / width + (y + structure.height) / height;
        let rgba;
        if (c >= structure.c[0] && c < structure.c[1] && r >= structure.r[0] && r < structure.r[1]) {
          rgba = sample('paving', c, r);
        } else {
          // Only the visible longitudinal face is included. Internal end faces
          // would create dark seams when the same segment repeats along its axis.
          const along = x / (width / 2) - (structure.face === 'c-min' ? structure.c[0] : structure.r[1]);
          const inside = structure.face === 'c-min'
            ? along >= structure.r[0] && along < structure.r[1]
            : along >= structure.c[0] && along < structure.c[1];
          const top = (structure.face === 'c-min' ? along - structure.c[0] : structure.r[1] - along) * height / 2 - structure.height;
          const depth = y - top;
          if (inside && depth >= 0 && depth < structure.height) {
            rgba = sample('wall', along, depth / (height * 2));
            if (structure.face === 'c-min') for (let channel = 0; channel < 3; channel++) rgba[channel] = Math.round(rgba[channel] * 0.84);
          }
        }
        if (rgba) {
          pixels.data.set(rgba, ((oy + py) * atlas.width + ox + px) * 4);
          visible++;
        }
      }
      textures[structure.id] = { image: 'ground', frame: { x: ox, y: oy, width: 80, height: 80 }, anchor: { x: rootX / 80, y: rootY / 80 } };
      structureCoverage.push({ id: structure.id, visible });
    }
    context.putImageData(pixels, 0, 0);
    return {
      png: atlas.toDataURL('image/png').split(',')[1],
      metadata: { version: 1, mode: 'blob47', tileWidth: width, tileHeight: height, imageWidth: atlas.width, imageHeight: atlas.height, variants, textures, structures: recipe.structures },
      sourceDimensions: { width: image.width, height: image.height }, counts, signatures, structureCoverage,
    };
  }, { encoded: source.toString('base64'), masks, recipe });
} finally { await browser.close(); }
if (new Set(result.signatures.slice(0, 47).map(item => item.signature)).size !== 47) throw new Error('Corner variants are not visually distinct at this raster resolution');
if (result.counts.some(item => item.visible !== 1024)) throw new Error('Unexpected ground diamond coverage');
await mkdir(outputURL, { recursive: true });
await writeFile(new URL('ground-atlas.png', outputURL), Buffer.from(result.png, 'base64'));
await writeFile(new URL('ground-tiles.json', outputURL), JSON.stringify(result.metadata, null, 2) + '\n');
await writeFile(new URL('ground-provenance.json', outputURL), JSON.stringify({
  source: '../../autotile-lab/art/material-source.png',
  sourceSHA256: createHash('sha256').update(source).digest('hex'),
  sourceDimensions: result.sourceDimensions, recipe,
  assembly: 'Existing genuinely generated flat material sheet, prefiltered to shared pixel density, mildly color graded and mirror sampled onto fixed 64x32 diamond geometry. Blob47 changes material margins only. Parapets and quay walls use projected rectangular caps and longitudinal stone faces; c-min faces receive consistent 0.84 shading. No independently generated finished tile claim.',
  limitations: 'Mirrored material repetition can be visible. Same-family grass/paving transition only; no universal terrain blending. Structure end faces are omitted for continuous repetition, so isolated endpoints need separate end caps. Alpha normalization is limited to the nearly opaque material sheet, not transparent props.',
  coverage: result.counts, signatures: result.signatures, structureCoverage: result.structureCoverage,
}, null, 2) + '\n');
console.log(`Prepared ${Object.keys(result.metadata.variants).length} path variants, grass, paved and ${recipe.structures.length} stone structures in ${result.metadata.imageWidth}x${result.metadata.imageHeight}: ${fileURLToPath(outputURL)}`);
