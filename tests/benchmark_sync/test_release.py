import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from src.benchmark_sync.release import DOCS, stage_release
from src.benchmark_sync.snapshot import digest

class ReleaseTests(unittest.TestCase):
    def package(self,extra=None):
        data={p:b'{}' for p in DOCS};data['src/benchmark_board/app.py']=b'pass\n'
        if extra: data.update(extra)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for p,value in data.items(): z.writestr(p,value)
        value=stream.getvalue()
        return {'release_id':digest(value),'size':len(value),'code_commit':'a'*40,
                'files':{p:{'sha256':digest(v),'size':len(v)} for p,v in data.items()}},value
    def test_safe_staging_and_corrupted_installed_cache(self):
        with tempfile.TemporaryDirectory() as root:
            m,data=self.package();p=stage_release(root,m,data)
            self.assertEqual(stage_release(root,m,data),p)
            (p/'src/benchmark_board/app.py').write_text('changed')
            with self.assertRaisesRegex(ValueError,'cache damaged'): stage_release(root,m,data)
    def test_traversal_and_altered_blob_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            m,data=self.package({'../escape.py':b'bad'})
            with self.assertRaises(ValueError): stage_release(root,m,data)
            m,data=self.package()
            with self.assertRaises(ValueError): stage_release(root,m,data+b'x')
            self.assertFalse((Path(root).parent/'escape.py').exists())
