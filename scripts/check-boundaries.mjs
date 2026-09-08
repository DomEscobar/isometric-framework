import { readFile, readdir } from 'node:fs/promises';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import ts from 'typescript';

const root = fileURLToPath(new URL('../src/', import.meta.url));
// Classify responsibilities, not individual allowed edges. New modules need an owner.
const groups = {
  headless: ['types.ts', 'core.ts', 'geometry.ts', 'levels.ts', 'scene.ts', 'model.ts',
    'pathfinding.ts', 'level-pathfinding.ts', 'physics.ts', 'events.ts', 'art.ts', 'autotiling.ts', 'interactions.ts', 'inventory.ts', 'saves.ts'],
  renderer: ['assets.ts', 'view.ts', 'sprites.ts'],
  controls: ['controls.ts', 'debug.ts'],
  orchestration: ['runtime.ts', 'index.ts'],
};
const owners = new Map(Object.entries(groups).flatMap(([group, files]) => files.map(file => [file, group])));
const allowed = {
  headless: ['headless'], renderer: ['headless', 'renderer'],
  controls: ['headless', 'controls'], orchestration: Object.keys(groups),
};

function inspect(file, source) {
  const failures = [];
  const owner = owners.get(file);
  if (!owner) return [`${file}: classify this module in scripts/check-boundaries.mjs`];
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const check = value => {
    if (!value || !ts.isStringLiteralLike(value)) {
      failures.push(`${file}: module imports must use a literal path so boundaries can be checked`);
      return;
    }
    const name = value.text;
    if (!name.startsWith('.')) {
      if (!(name === 'pixi.js' && ['renderer', 'orchestration'].includes(owner))) {
        failures.push(`${file}: ${owner} cannot import external module ${name}`);
      }
      return;
    }
    const target = relative(root, resolve(root, dirname(file), name)).split(sep).join('/');
    const targetOwner = owners.get(target);
    if (!targetOwner || !allowed[owner].includes(targetOwner)) {
      failures.push(`${file}: ${owner} cannot import ${name} (${targetOwner ?? 'outside classified src modules'})`);
    }
  };
  const visit = node => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      if (node.moduleSpecifier) check(node.moduleSpecifier);
    } else if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) {
      check(node.argument.literal);
    } else if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword
      || (ts.isIdentifier(node.expression) && node.expression.text === 'require'))) {
      check(node.arguments[0]);
    } else if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
      check(node.moduleReference.expression);
    }
    ts.forEachChild(node, visit);
  };
  visit(tree);
  return failures;
}

if (process.argv.includes('--self-test')) {
  const probes = [
    ['model.ts', "import type { Cell } from './types.ts'", true],
    ['view.ts', "import { Graphics } from 'pixi.js'", true],
    ['model.ts', "export * from './view.ts'", false],
    ['physics.ts', "import('pixi.js')", false],
    ['runtime.ts', "import '../demo/scenes.ts'", false],
    ['controls.ts', "type T = import('./runtime.ts').Runtime", false],
    ['core.ts', "import(otherPath)", false],
    ['new-system.ts', '', false],
  ];
  for (const [file, source, pass] of probes) assert.equal(inspect(file, source).length === 0, pass, source);
  console.log(`Module boundary checker: ${probes.length} positive/negative probes passed.`);
} else {
  const files = (await readdir(root, { recursive: true })).filter(file => file.endsWith('.ts'));
  const failures = [];
  for (const file of files) failures.push(...inspect(file.split(sep).join('/'), await readFile(resolve(root, file), 'utf8')));
  if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }
  else console.log(`Module boundaries passed for ${files.length} source modules.`);
}
