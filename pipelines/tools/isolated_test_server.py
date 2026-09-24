"""Disposable zero-budget fixture server; never changes the live project policy."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from app import create_app
from generation import DEFAULT_POLICY
if __name__=='__main__':
 with tempfile.TemporaryDirectory(prefix='terrain-browser-fixtures-') as directory:
  uvicorn.run(create_app(directory,policy=DEFAULT_POLICY.copy()),host='127.0.0.1',port=int(sys.argv[1]))
