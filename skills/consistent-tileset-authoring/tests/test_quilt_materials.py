"""Offline synthetic algorithm fixtures; not production artwork."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'quilt_materials.py'


class QuiltTests(unittest.TestCase):
    def test_deterministic_non_square_quilt_copies_source_pixels(self):
        self.assertTrue(SCRIPT.is_file(), 'packaged quilting helper is missing')
        spec = importlib.util.spec_from_file_location('quilt_materials', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = np.random.default_rng(4).integers(0, 256, (13, 19, 3), dtype=np.uint8)
        a, stats = module.quilt(source, 41, 27, 7, 8, 3, 5)
        b, _ = module.quilt(source, 41, 27, 7, 8, 3, 5)
        np.testing.assert_array_equal(a, b)
        different, _ = module.quilt(source, 41, 27, 8, 8, 3, 5)
        self.assertFalse(np.array_equal(a, different))
        self.assertEqual(a.shape, (27, 41, 3))
        colors = set(map(tuple, source.reshape(-1, 3)))
        self.assertTrue(all(tuple(p) in colors for p in a.reshape(-1, 3)))
        self.assertGreater(stats['patches'], 1)
        for args in [(True, 2, 0, 4, 1, 1), (2, 2, 0, 20, 1, 1), (2, 2, 0, 4, 4, 1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                module.quilt(source, *args)
        cost = np.array([[9, 1, 9], [9, 9, 1], [9, 1, 9]])
        np.testing.assert_array_equal(module.minimum_cut(cost), [1, 2, 1])


class RecipeTests(unittest.TestCase):
    def test_recipe_cli_exports_binding_compatible_cache(self):
        import tempfile, json, subprocess, sys
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (16, 16), (10, 80, 20)).save(root / 'a.png')
            Image.new('RGB', (16, 16), (140, 100, 50)).save(root / 'b.png')
            recipe = {'version': 1, 'map': {'columns': 3, 'rows': 2, 'tileWidth': 8, 'tileHeight': 4},
                      'cells': [['a', 'b', 'a'], ['b', 'a', 'b']],
                      'materials': {'a': {'source': 'a.png'}, 'b': {'source': 'b.png'}},
                      'seed': 7, 'patch': 8, 'overlap': 2, 'candidates': 3}
            (root / 'recipe.json').write_text(json.dumps(recipe))
            cli = SCRIPT.with_name('quilt-materials.py')
            self.assertTrue(cli.is_file(), 'quilting recipe CLI is missing')
            for name in ['one', 'two']:
                result = subprocess.run([sys.executable, '-B', str(cli), str(root / 'recipe.json'), '--out', str(root / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'one/ground.png').read_bytes(), (root / 'two/ground.png').read_bytes())
            pack = json.loads((root / 'one/packed-art.json').read_text())
            self.assertEqual(pack['groups'][0]['composition']['origin'], [-4, -6])
            with Image.open(root / 'one/ground.png') as image:
                self.assertEqual(image.size, (20, 10))
            provenance = json.loads((root / 'one/provenance.json').read_text())
            self.assertEqual(provenance['cellCounts'], {'a': 3, 'b': 3})
            self.assertNotIn(tmp, json.dumps(provenance))
            (root / 'invalid.json').write_text('{"version":99}')
            rejected = subprocess.run([sys.executable, '-B', str(cli), str(root / 'invalid.json'), '--out', str(root / 'invalid-out')], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('quilt-materials:', rejected.stderr)
            self.assertNotIn('Traceback', rejected.stderr)
            self.assertFalse((root / 'invalid-out').exists())
            with Image.open(root / 'one/ground.png') as image:
                pixels = np.array(image)
            self.assertEqual(tuple(pixels[6, 4]), (10, 80, 20))
            self.assertEqual(tuple(pixels[4, 8]), (140, 100, 50))


    def test_density_mask_validation_and_large_map(self):
        import tempfile, json, copy, sys
        from PIL import Image
        sys.path.insert(0, str(SCRIPT.parent))
        from quilt_materials import run
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (16, 16), (1, 2, 3)).save(root / 'a.png')
            Image.new('RGB', (16, 16), (4, 5, 6)).save(root / 'b.png')
            recipe = {'version': 1, 'map': {'columns': 3, 'rows': 2, 'tileWidth': 8, 'tileHeight': 4},
                      'cells': [['a', 'b', 'a'], ['b', 'a', 'b']], 'sourceScale': 2,
                      'materials': {'a': {'source': 'a.png'}, 'b': {'source': 'b.png'}},
                      'seed': 0, 'patch': 8, 'overlap': 2, 'candidates': 1}
            path = root / 'recipe.json'
            def compile(value, name):
                path.write_text(json.dumps(value))
                return run(path, root / name)
            result = compile(recipe, 'density')
            self.assertEqual(result['bounds']['width'], 40)
            self.assertEqual(result['bounds']['height'], 20)
            Image.new('L', (40, 20), 1).save(root / 'mask.png')
            masked = dict(recipe, materialMask='mask.png')
            compile(masked, 'masked')
            with Image.open(root / 'masked/ground.png') as image:
                self.assertTrue(np.all(np.array(image) == [4, 5, 6]))
            invalid = [('seed', -1), ('seed', True), ('patch', 17), ('overlap', 8), ('candidates', 0),
                       ('sourceScale', 1.5), ('cells', [['missing']]), ('version', 2), ('extra', 1),
                       ('materials', {'a': {'source': 'a.png'}})]
            for index, (key, value) in enumerate(invalid):
                bad = copy.deepcopy(recipe); bad[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    compile(bad, f'bad{index}')
                self.assertFalse((root / f'bad{index}').exists())
            for source in ['missing.png', '../escape.png', str(root / 'a.png'), 'bad.png']:
                (root / 'bad.png').write_text('not a PNG')
                bad = copy.deepcopy(recipe); bad['materials']['a']['source'] = source
                with self.subTest(source=source), self.assertRaises(ValueError):
                    compile(bad, 'badsource')
            for key, value in [('columns', 0), ('rows', -1), ('tileWidth', 7), ('tileHeight', True), ('columns', 257)]:
                bad = copy.deepcopy(recipe); bad['map'][key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    compile(bad, 'baddim')
            Image.new('RGBA', (16, 16), (1, 2, 3, 128)).save(root / 'alpha.png')
            bad = copy.deepcopy(recipe); bad['materials']['a']['source'] = 'alpha.png'
            with self.assertRaisesRegex(ValueError, 'opaque'):
                compile(bad, 'badalpha')
            Image.new('L', (39, 20), 1).save(root / 'mask.png')
            with self.assertRaisesRegex(ValueError, 'canvas-sized'):
                compile(masked, 'wrongsize')
            Image.new('L', (40, 20), 2).save(root / 'mask.png')
            with self.assertRaisesRegex(ValueError, 'unknown material index'):
                compile(masked, 'badmask')
            large = dict(recipe, sourceScale=1,
                         map={'columns': 60, 'rows': 60, 'tileWidth': 2, 'tileHeight': 2},
                         cells=[['a', 'b'] * 30 for _ in range(60)])
            result = compile(large, 'large')
            self.assertEqual(result['bounds']['cells'], 3600)
            self.assertEqual(sum(result['cellCounts'].values()), 3600)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                compile(large, 'large')


if __name__ == '__main__':
    unittest.main()
