"""Neutral motion fixtures test measurements, not aesthetic acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/inspect-motion.py'
SPEC = importlib.util.spec_from_file_location('motion', SCRIPT)
motion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(motion)


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        moving = Image.new('L', (4,2))
        moving.putpixel((0,0),255)
        moving.save(self.root/'moving.png')
        fixed = Image.new('L',(4,2))
        fixed.putpixel((3,1),255)
        fixed.save(self.root/'fixed.png')
        self.images = [Image.new('RGBA',(4,2),(20,30,40,0)) for _ in range(3)]
        self.images[1].putpixel((0,0),(21,30,40,0))
        self.recipe = {'version':1,'periodSeconds':1,'maxSampleGapSeconds':0.5,
                       'movingMask':'moving.png','fixedMask':'fixed.png',
                       'frames':[{'time':t,'file':f'{i}.png'} for i,t in enumerate((0,0.5,1))]}

    def run_inspect(self, name='out'):
        for i,image in enumerate(self.images):
            image.save(self.root/f'{i}.png')
        recipe = self.root/'recipe.json'
        recipe.write_text(json.dumps(self.recipe))
        return motion.inspect(recipe,self.root/name)

    def test_small_rgb_change_under_transparent_alpha_is_not_exact_equality(self):
        report = self.run_inspect()
        self.assertTrue(report['observedMovingChange'])
        self.assertEqual(report['adjacentPairs'][0]['moving']['exactChangedPixels'],1)
        self.assertEqual(report['adjacentPairs'][0]['moving']['aboveThresholdPixels'],0)
        self.assertEqual(report['endpoint']['moving']['exactChangedPixels'],0)
        self.assertEqual(report['maximumFixedDriftPixelsFromStart'],0)
        self.assertEqual(report['visualVerdict'],'unverified')
        self.assertEqual(report['unmeasuredPixels'],6)
        self.assertTrue((self.root/'out/board.png').is_file())

    def test_frozen_sequence_drift_and_bad_wrap_are_distinct(self):
        self.images[1] = self.images[0].copy()
        report = self.run_inspect('frozen')
        self.assertFalse(report['observedMovingChange'])
        self.images[1].putpixel((3,1),(200,30,40,0))
        self.images[2].putpixel((0,0),(90,30,40,0))
        report = self.run_inspect('drift')
        self.assertEqual(report['maximumFixedDriftPixelsFromStart'],1)
        self.assertEqual(report['endpoint']['moving']['aboveThresholdPixels'],1)
        self.assertEqual(report['endpoint']['fixed']['exactChangedPixels'],0)

    def test_sparse_samples_remain_explicit_and_fixed_mask_optional(self):
        self.recipe.pop('maxSampleGapSeconds')
        self.recipe.pop('fixedMask')
        report = self.run_inspect()
        self.assertFalse(report['sampling']['withinDeclaredGap'])
        self.assertIsNone(report['maximumFixedDriftPixelsFromStart'])

    def test_invalid_times_and_unknown_fields_rejected_without_outputs(self):
        original = copy.deepcopy(self.recipe)
        cases = [lambda r:r['frames'][1].update(time=0),
                 lambda r:r['frames'][2].update(time=0.9),
                 lambda r:r.update(periodSeconds=float('nan')),
                 lambda r:r.update(threshold=True),
                 lambda r:r.update(unknown='typo')]
        for i,change in enumerate(cases):
            with self.subTest(i=i):
                self.recipe = copy.deepcopy(original)
                change(self.recipe)
                with self.assertRaises(ValueError):
                    self.run_inspect(str(i))
                self.assertFalse((self.root/str(i)).exists())

    def test_mask_mismatch_overlap_and_nonbinary_rejected(self):
        for i,mask in enumerate([Image.new('L',(3,2),255), Image.new('L',(4,2),255), Image.new('L',(4,2),100)]):
            mask.save(self.root/'fixed.png')
            with self.assertRaises(ValueError):
                self.run_inspect(str(i))

    def test_repeatable_report_and_no_overwrite(self):
        a = self.run_inspect('a')
        b = self.run_inspect('b')
        self.assertEqual(a,b)
        with self.assertRaisesRegex(ValueError,'must be new'):
            self.run_inspect('a')


if __name__ == '__main__':
    unittest.main()
