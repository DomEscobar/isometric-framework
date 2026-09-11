"""Measure supplied timed PNG frames; no capture, generation or visual verdict.

Python/Pillow authoring helper. Use explicit binary masks in capture coordinates.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter

from PIL import Image, ImageChops, ImageDraw

MAX_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 512_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(base, name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name
            and not Path(name).is_absolute(), 'Use local relative forward-slash paths')
    return (base / name).resolve()


def number(value, low, high, label):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f'{label} must be finite in [{low}, {high}]')
    return value


def read_png(path, inputs, mask=False):
    require(path.stat().st_size <= 64*1024*1024, f'PNG exceeds 64 MiB: {path}')
    before = sha(path)
    with Image.open(path) as image:
        require(image.format == 'PNG' and getattr(image, 'n_frames', 1) == 1
                and image.width*image.height <= MAX_PIXELS, f'Expected bounded static PNG: {path}')
        if mask:
            require(image.mode in ('1', 'L'), f'Mask must be grayscale PNG: {path}')
            decoded = image.convert('L')
            require(not any(decoded.histogram()[1:255]), f'Mask must be binary 0/255: {path}')
        else:
            decoded = image.convert('RGBA')
    require(sha(path) == before, f'Input changed while decoding: {path}')
    inputs[str(path)] = before
    return decoded


def differences(a, b, mask, threshold):
    channels = ImageChops.difference(a, b).split()
    maximum = channels[0]
    for channel in channels[1:]:
        maximum = ImageChops.lighter(maximum, channel)
    hist = ImageChops.multiply(maximum, mask).histogram()
    return {'exactChangedPixels': sum(hist[1:]),
            'aboveThresholdPixels': sum(hist[threshold+1:]),
            'maximumChannelDifference': max(i for i, count in enumerate(hist) if count)}


def inspect(spec_path, output):
    started = perf_counter()
    spec_path, output = Path(spec_path).resolve(), Path(output).resolve()
    require(not output.exists(), 'Output directory must be new')
    require(spec_path.stat().st_size <= 1_048_576, 'Recipe exceeds 1 MiB')
    recipe_hash = sha(spec_path)
    spec = json.loads(spec_path.read_text(encoding='utf-8-sig'))
    require(type(spec) is dict and set(spec) <= {
        'version', 'frames', 'periodSeconds', 'movingMask', 'fixedMask', 'threshold', 'maxSampleGapSeconds'
    }, 'Unknown motion recipe fields')
    require(type(spec.get('version')) is int and spec['version'] == 1, 'version must be 1')
    period = number(spec['periodSeconds'], 0.000001, 86400, 'periodSeconds')
    gap = number(spec.get('maxSampleGapSeconds', period/8), 0.000001, period, 'maxSampleGapSeconds')
    threshold = spec.get('threshold', 8)
    require(type(threshold) is int and 0 <= threshold <= 255, 'threshold must be integer 0..255')
    frames = spec['frames']
    require(isinstance(frames, list) and 3 <= len(frames) <= 256, 'Supply 3..256 timed frames')
    times = []
    paths = []
    for frame in frames:
        require(type(frame) is dict and set(frame) == {'time', 'file'}, 'Each frame needs time and file')
        times.append(number(frame['time'], 0, period, 'frame time'))
        paths.append(local(spec_path.parent, frame['file']))
    require(all(a < b for a, b in zip(times, times[1:])), 'Frame times must strictly increase')
    require(times[0] == 0 and abs(times[-1]-period) <= 1e-8,
            'Capture time 0 and the endpoint at the declared period')
    inputs = {str(spec_path): recipe_hash, str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    moving = read_png(local(spec_path.parent, spec['movingMask']), inputs, mask=True)
    fixed = read_png(local(spec_path.parent, spec['fixedMask']), inputs, mask=True) if spec.get('fixedMask') else None
    require(moving.getbbox() is not None, 'Moving mask must be nonempty')
    if fixed is not None:
        require(fixed.size == moving.size and fixed.getbbox() is not None, 'Fixed mask size/coverage invalid')
        require(ImageChops.multiply(fixed, moving).getbbox() is None, 'Moving and fixed masks overlap')
    require(moving.width*moving.height*len(frames) <= MAX_TOTAL_PIXELS, 'Sequence exceeds total pixel budget')
    require(all(not path.is_relative_to(output) for path in [*paths, *map(Path, inputs)]),
            'Output must not contain input paths')
    selected = sorted({round(i*(len(frames)-1)/7) for i in range(8)})
    board = Image.new('RGB', (768, 360), '#23312c')
    draw = ImageDraw.Draw(board)
    pairs, first, previous = [], None, None
    fixed_drift = 0
    changed_from_first = 0
    for index, path in enumerate(paths):
        current = read_png(path, inputs)
        require(current.size == moving.size, f'Frame/mask dimensions disagree: {path}')
        if first is None:
            first = current
        changed_from_first = max(changed_from_first, differences(first, current, moving, threshold)['exactChangedPixels'])
        if fixed is not None:
            fixed_drift = max(fixed_drift, differences(first, current, fixed, threshold)['exactChangedPixels'])
        if previous is not None:
            pairs.append({'from': times[index-1], 'to': times[index],
                          'moving': differences(previous, current, moving, threshold),
                          'fixed': differences(previous, current, fixed, threshold) if fixed is not None else None})
        if index in selected:
            slot = selected.index(index)
            thumb = current.copy()
            thumb.thumbnail((184, 144), Image.Resampling.NEAREST)
            x, y = (slot % 4)*192+4, (slot//4)*180+4
            board.paste(thumb.convert('RGB'), (x,y))
            draw.text((x,y+148), f't={times[index]:g}s', fill='white')
        previous = current
    endpoint = {'moving': differences(first, previous, moving, threshold),
                'fixed': differences(first, previous, fixed, threshold) if fixed is not None else None}
    actual_gap = max(b-a for a,b in zip(times,times[1:]))
    moving_count = moving.histogram()[255]
    fixed_count = fixed.histogram()[255] if fixed is not None else 0
    report = {
        'version': 1, 'visualVerdict': 'unverified', 'inputs': inputs,
        'dimensions': list(moving.size), 'frameCount': len(frames), 'periodSeconds': period,
        'threshold': threshold, 'movingPixels': moving_count, 'fixedPixels': fixed_count,
        'unmeasuredPixels': moving.width*moving.height-moving_count-fixed_count,
        'sampling': {'maximumGapSeconds': actual_gap, 'allowedGapSeconds': gap,
                     'withinDeclaredGap': actual_gap <= gap+1e-8},
        'observedMovingChange': changed_from_first > 0,
        'maximumFixedDriftPixelsFromStart': fixed_drift if fixed is not None else None,
        'endpoint': endpoint, 'adjacentPairs': pairs,
        'limit': 'Supplied timestamps are not authenticated. Exact differences include all RGBA channels. '
                 'Masked samples do not certify playback, speed, direction, pause, geometry or a visually seamless wrap.'
    }
    require(all(sha(Path(path)) == digest for path,digest in inputs.items()), 'Inputs changed during inspection')
    output.mkdir(parents=True, exist_ok=False)
    board.save(output/'board.png')
    overlay = first.convert('RGB')
    overlay.paste((40,190,110), mask=moving.point(lambda v: v//3))
    if fixed is not None:
        overlay.paste((240,70,70), mask=fixed.point(lambda v: v//3))
    overlay.save(output/'regions.png')
    report['artifacts'] = {name: sha(output/name) for name in ('board.png', 'regions.png')}
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n', encoding='utf-8')
    (output/'timings.json').write_text(json.dumps({'elapsedSeconds': perf_counter()-started})+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.recipe, args.out)
        print(json.dumps({key: report[key] for key in (
            'visualVerdict', 'frameCount', 'sampling', 'observedMovingChange', 'maximumFixedDriftPixelsFromStart', 'endpoint'
        )},indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'inspect-motion: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
