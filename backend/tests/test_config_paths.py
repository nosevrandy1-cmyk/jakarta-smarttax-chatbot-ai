import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BACKEND=Path(__file__).resolve().parents[1]


class ConfigPathTests(unittest.TestCase):
    def resolve_from(self, cwd, chroma, uploads):
        env={**os.environ,'PYTHONPATH':str(BACKEND),'CHROMA_PERSIST_DIR':chroma,'JST_UPLOAD_DIR':uploads}
        code='from app.config import CHROMA_STORAGE_DIR,UPLOAD_STAGING_DIR; import json; print(json.dumps([str(CHROMA_STORAGE_DIR),str(UPLOAD_STAGING_DIR)]))'
        return json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=cwd,env=env,text=True))

    def test_relative_paths_resolve_identically_from_other_directories(self):
        with tempfile.TemporaryDirectory() as other:
            a=self.resolve_from(BACKEND,'./smarttax_vectordb','data/uploads')
            b=self.resolve_from(other,'./smarttax_vectordb','data/uploads')
            self.assertEqual(a,b)
            self.assertEqual(Path(a[0]),BACKEND/'smarttax_vectordb')
            self.assertEqual(Path(a[1]),BACKEND/'data/uploads')

    def test_absolute_overrides_are_preserved(self):
        with tempfile.TemporaryDirectory() as other:
            chroma=str(Path(other)/'vectors');uploads=str(Path(other)/'originals')
            self.assertEqual(self.resolve_from(BACKEND,chroma,uploads),[chroma,uploads])
