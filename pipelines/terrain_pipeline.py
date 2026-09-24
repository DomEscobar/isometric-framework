"""Slim terrain route: description -> TerrainSpec -> grid -> guide -> painting -> review -> scene artifact.

Every stage writes one file into the run directory and is skipped when that file exists, so a rerun resumes
without buying anything twice. One ledger bounds all paid calls of the run.
"""
import json
import subprocess
from pathlib import Path

from artifacts import canonical, digest
from hybrid_artifact import ROOT, build_scene
from hybrid_painted_scene import guide_png, inventory
from terrain_intent import plan_terrain
from terrain_llm import Ledger
from terrain_review import review, verdict

ROUTE = 'terrain-spec/1'


class NotAccepted(ValueError):
    pass


def browser_probe(directory):
    result = subprocess.run(['node', str(ROOT / 'tools/hybrid_artifact_probe.mjs'), str(directory)], capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('Browser-/Exportverifikation fehlgeschlagen: ' + result.stderr.decode()[-400:])
    return json.loads((Path(directory) / 'browser-proof.json').read_text())


class TerrainPipeline:
    def __init__(self, run_dir, planner, reviewer, painter, probe=browser_probe):
        self.d, self.planner, self.reviewer, self.painter, self.probe = Path(run_dir), planner, reviewer, painter, probe
        self.request = json.loads((self.d / 'request.json').read_text())
        self.ledger = Ledger(self.d / 'ledger.jsonl', self.request['max_usd'])

    def _json(self, name):
        path = self.d / name
        return json.loads(path.read_text()) if path.exists() else None

    def _write(self, name, value):
        (self.d / name).write_bytes(value if isinstance(value, bytes) else json.dumps(value, indent=1, ensure_ascii=False).encode())

    def _world(self):
        if not (self.d / 'world.json').exists():
            r = self.request
            spec, world, history = plan_terrain(r['description'], r['width'], r['height'], self.planner, self.ledger)
            self._write('intent.json', history)
            self._write('spec.json', spec.model_dump())
            self._write('world.json', world)
            self._write('guide.png', guide_png(world))
        return self._json('world.json'), (self.d / 'guide.png').read_bytes()

    def _painting(self, attempt, world, guide, correction, rejected):
        image = self.d / f'paint-{attempt}.png'
        if not image.exists():
            ticket = self._json(f'paint-{attempt}.ticket.json')
            if ticket is None:
                ticket = self.painter.submit(self.ledger, f'paint-{attempt}', world, guide, correction, rejected)
                self._write(f'paint-{attempt}.ticket.json', ticket)
            self._write(image.name, self.painter.collect(self.ledger, ticket))
        return image.read_bytes()

    def _review(self, attempt, world, guide, painting):
        stored = self._json(f'review-{attempt}.json')
        if stored is None:
            result = review(self.reviewer, self.ledger, f'review-{attempt}', world, guide, painting)
            accepted, correction, cosmetic = verdict(result)
            stored = {'accepted': accepted, 'correction': correction, 'cosmetic': cosmetic, 'painting_sha256': digest(painting),
                      **result.model_dump()}
            self._write(f'review-{attempt}.json', stored)
        return stored['accepted'], stored['correction']

    def _package(self, attempt, world, painting):
        out = self.d / 'artifact'
        if not (out / 'browser-proof.json').exists():
            r = self.request
            provenance = {'route': ROUTE, 'description': r['description'], 'planner': self.planner.model, 'reviewer': self.reviewer.model,
                          'painter': self.painter.model, 'accepted_attempt': attempt, 'inventory': inventory(world),
                          'cosmetic_findings': self._json(f'review-{attempt}.json')['cosmetic'],
                          'spec_sha256': digest(canonical(self._json('spec.json'))), 'spent_usd': str(self.ledger.spent())}
            build_scene(out, world, painting, provenance)
            self.probe(out)
        return out

    def run(self):
        world, guide = self._world()
        correction = painting = None
        for attempt in range(self.request['max_images']):
            painting = self._painting(attempt, world, guide, correction, painting)
            accepted, correction = self._review(attempt, world, guide, painting)
            if accepted:
                return self._package(attempt, world, painting)
        raise NotAccepted(f"Kein Bild nach {self.request['max_images']} Versuchen abgenommen; letzte Befunde: {correction}")


def main(argv=None):
    import argparse
    from terrain_llm import StructuredModel
    from terrain_paint import ScenePainter
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('run_dir')
    init.add_argument('--description-file', required=True)
    init.add_argument('--width', type=int, default=18)
    init.add_argument('--height', type=int, default=16)
    init.add_argument('--max-usd', default='0.10')
    init.add_argument('--max-images', type=int, default=2)
    init.add_argument('--planner', default='openai/gpt-6-luna-pro')
    init.add_argument('--reviewer', default='google/gemini-3.8-flash')
    run = sub.add_parser('run')
    run.add_argument('run_dir')
    run.add_argument('--paid', action='store_true', help='required: this command buys model calls and images')
    args = parser.parse_args(argv)
    d = Path(args.run_dir)
    if args.command == 'init':
        d.mkdir(parents=True, exist_ok=False)
        (d / 'request.json').write_text(json.dumps({
            'route': ROUTE, 'description': Path(args.description_file).read_text().strip(), 'width': args.width,
            'height': args.height, 'max_usd': args.max_usd, 'max_images': args.max_images,
            'planner': args.planner, 'reviewer': args.reviewer}, indent=1, ensure_ascii=False))
        return
    if not args.paid:
        raise SystemExit('run kauft Modellaufrufe und Bilder; mit --paid bestätigen')
    request = json.loads((d / 'request.json').read_text())
    pipeline = TerrainPipeline(d, StructuredModel(request['planner']), StructuredModel(request['reviewer']), ScenePainter())
    print(json.dumps({'artifact': str(pipeline.run()), 'spent_usd': str(pipeline.ledger.spent())}))


if __name__ == '__main__':
    main()
