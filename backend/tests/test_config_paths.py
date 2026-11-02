import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BACKEND=Path(__file__).resolve().parents[1]


class ConfigPathTests(unittest.TestCase):
    def resolve_from(self, cwd, vectors, uploads):
        env={**os.environ,'PYTHONPATH':str(BACKEND),'QDRANT_STORAGE_DIR':vectors,'JST_UPLOAD_DIR':uploads}
        code='from app.config import QDRANT_STORAGE_DIR,UPLOAD_STAGING_DIR; import json; print(json.dumps([str(QDRANT_STORAGE_DIR),str(UPLOAD_STAGING_DIR)]))'
        return json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=cwd,env=env,text=True))

    def test_relative_paths_resolve_identically_from_other_directories(self):
        with tempfile.TemporaryDirectory() as other:
            a=self.resolve_from(BACKEND,'./qdrant_knowledge_storage','data/uploads')
            b=self.resolve_from(other,'./qdrant_knowledge_storage','data/uploads')
            self.assertEqual(a,b)
            self.assertEqual(Path(a[0]),BACKEND/'qdrant_knowledge_storage')
            self.assertEqual(Path(a[1]),BACKEND/'data/uploads')

    def test_absolute_overrides_are_preserved(self):
        with tempfile.TemporaryDirectory() as other:
            vectors=str(Path(other)/'vectors');uploads=str(Path(other)/'originals')
            self.assertEqual(self.resolve_from(BACKEND,vectors,uploads),[vectors,uploads])
