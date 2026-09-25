import subprocess
import tempfile
import unittest
from pathlib import Path

from src.benchmark_sync.git_fast import FastGitError, GitFastLane
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

    def test_known_fetched_head_saves_lookup_but_cannot_force_stale_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);remote=root/'remote.git'
            subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
            writer=GitFastLane(root/'writer','test/repo')
            rival=GitFastLane(root/'rival','test/repo')
            for lane in (writer,rival):lane._run(['remote','set-url','origin',str(remote)])
            first=b'{"generation":1}';first_delta=b'first'
            first_path='deltas/'+digest(first_delta)+'.json.gz'
            base=writer.update({'channels/fast.json':first,first_path:first_delta})
            self.assertEqual(writer.head(),base)
            second=b'{"generation":2}';second_delta=b'second'
            second_path='deltas/'+digest(second_delta)+'.json.gz'
            rival_commit=rival.update({'channels/fast.json':second,second_path:second_delta},expected=first)
            third=b'{"generation":3}';third_delta=b'third'
            third_path='deltas/'+digest(third_delta)+'.json.gz'
            with self.assertRaises(FastGitError):
                writer.update({'channels/fast.json':third,third_path:third_delta},
                              expected=first,known_head=base)
            self.assertEqual(rival.head(),rival_commit)
            self.assertEqual(rival.read_path(rival_commit,'channels/fast.json'),second)


if __name__=='__main__': unittest.main()
