"""Free offline diagnostic. Does NOT instantiate the app or touch its SQLite ledger."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artifacts import canonical, digest, export_files
from registration_diagnostic import diagnose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--layout', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    # Never write under live data, including through an output symlink.
    data = Path(__file__).resolve().parents[1]/'data'
    if args.output.resolve().is_relative_to(data.resolve()):
        parser.error('output must be outside live data')
    raw, layout_raw = args.source.read_bytes(), args.layout.read_bytes()
    layout = json.loads(layout_raw)
    result, overlay = diagnose(raw, export_files(layout))
    result.update(layout_revision=digest(canonical(layout)), source_path=str(args.source.resolve()),
                  layout_path=str(args.layout.resolve()), layout_file_sha256=digest(layout_raw))
    args.output.mkdir(parents=True, exist_ok=True)
    # Exclusive output creation: do not silently overwrite retained diagnostic runs.
    with (args.output/'diagnosis.json').open('xb') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False).encode())
    with (args.output/'overlay-native.png').open('xb') as f:
        overlay.save(f, format='PNG')
    print(json.dumps(dict(output=str(args.output), proposed_fit=result['proposed_fit'],
                          legacy_blocker=result['legacy_registration'].get('blocker'),
                          production_approved=False)))


if __name__ == '__main__':
    main()
