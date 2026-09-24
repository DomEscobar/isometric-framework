from pathlib import Path
from time import monotonic
import sys
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quality_gates
path = Path('artifacts/minimax-ne-source-01/native-frames/frame-0043.png')
start = monotonic()
with Image.open(path) as opened:
    feature = quality_gates._motion_feature(opened.convert('RGBA'))
print(monotonic() - start, {key: value for key, value in feature.items() if key != 'normalized'})
feature['normalized'].close()
