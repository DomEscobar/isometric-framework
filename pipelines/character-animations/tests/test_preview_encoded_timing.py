import json
import subprocess
from PIL import Image
import spatial_export


def test_encoded_preview_retains_full_action_and_last_hold(tmp_path):
    source = tmp_path / 'export-80'
    source.mkdir()
    durations = [2/24, 5/24, 5/24, 3/24, 4/24, 5/24, 7/24, 8/24]
    for i in range(8):
        Image.new('RGBA', (80, 80), (i*30, 80, 30, 255)).save(source / f'frame-{i:04d}.png')
    name = spatial_export._encode_preview(tmp_path, 80, 8/sum(durations), 8, loop=False, frame_durations_seconds=durations)
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration:format=duration','-of','json',str(tmp_path/name)]))
    expected = 3 * sum(durations)
    assert abs(float(probe['format']['duration']) - expected) <= 1/120
    assert abs(float(probe['streams'][0]['duration']) - expected) <= 1/120
    # Decode every presentation frame, including the final hold. Synthetic
    # colors are a test fixture only; they reveal reordered/missing poses.
    raw = subprocess.check_output(['ffmpeg','-v','error','-i',str(tmp_path/name),'-f','rawvideo','-pix_fmt','rgb24','-'])
    stride = 80 * 80 * 3
    assert len(raw) // stride == round(expected * 120)
    boundaries = []
    end = 0
    for _ in range(3):
        for i, duration in enumerate(durations):
            start = end
            end += duration
            middle = int(((start + end) / 2) * 120)
            assert abs(raw[middle * stride] - i * 30) < 8
