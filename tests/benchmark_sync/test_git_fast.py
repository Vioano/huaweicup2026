import subprocess
import tempfile
import unittest
from pathlib import Path

from src.benchmark_sync.git_fast import GitFastLane
from src.benchmark_sync.snapshot import digest


class GitFastLaneTests(unittest.TestCase):
    def test_small_branch_push_fetch_and_replace_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);remote=root/'remote.git'
            subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
            writer=GitFastLane(root/'writer','test/repo')
            reader=GitFastLane(root/'reader','test/repo')
            writer._run(['remote','set-url','origin',str(remote)])
            reader._run(['remote','set-url','origin',str(remote)])
            first=b'{"generation":1}'
            delta=b'first compressed delta'
            path='deltas/'+digest(delta)+'.json.gz'
            commit=writer.update({'channels/fast.json':first,path:delta},expected=None)
            self.assertEqual(reader.head(),commit)
            self.assertEqual(reader.read_path(commit,'channels/fast.json'),first)
            self.assertEqual(reader.read_path(commit,path),delta)
            self.assertEqual(writer.update({'channels/fast.json':first,path:delta},expected=first),commit)
            second=b'{"generation":2}'
            newer=b'second compressed delta'
            newer_path='deltas/'+digest(newer)+'.json.gz'
            next_commit=writer.update({'channels/fast.json':second,newer_path:newer},expected=first)
            self.assertNotEqual(next_commit,commit)
            self.assertEqual(reader.head(),next_commit)
            self.assertEqual(reader.read_path(next_commit,'channels/fast.json'),second)
            self.assertEqual(reader.read_path(next_commit,newer_path),newer)
            with self.assertRaises(FileNotFoundError):
                reader.read_path(next_commit,path)
            with self.assertRaisesRegex(ValueError,'changed'):
                writer.update({'channels/fast.json':b'stale',path:delta},expected=first)


if __name__=='__main__': unittest.main()
