"""Run all tests from disposable source; never import legacy app against live data."""
import os,sys,tempfile,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hybrid-isolated-suite-') as tmp:
    out=Path(tmp)
    for p in ROOT.iterdir():
        if p.is_file() and p.suffix in ['.py','.md','.txt']:shutil.copyfile(p,out/p.name)
    for folder in ['tests','static','tools']:
        shutil.copytree(ROOT/folder,out/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for n in ['evidence/paid-pilot/layout-response.json','evidence/hybrid-multilevel/artifact/world.json','evidence/hybrid-multilevel/generation/provider-original.png','evidence/hybrid-multilevel/generation/style-reference.png','experiments/hybrid-multilevel/crops.json']:
        p=out/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,p)
    shutil.copytree(ROOT/'evidence/water-reference/character/artifact',out/'evidence/water-reference/character/artifact')
    args=sys.argv[1:] or ['tests','-q']
    result=subprocess.run([sys.executable,'-m','pytest',*args],cwd=out,capture_output=True,text=True,timeout=500,env={**os.environ,'PYTHONPATH':str(out)})
    output=result.stdout+result.stderr
    p=Path(os.environ.get('HYBRID_TEST_LOG',str(ROOT/'evidence/autonomous-hybrid/tests-final.txt')));p.parent.mkdir(exist_ok=True,parents=True);p.write_text(output)
    print(output);sys.exit(result.returncode)
