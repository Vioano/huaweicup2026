import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.benchmark_sync.engine import write_json
from src.benchmark_sync.submission import discover, parse_worktree_heads


class SubmissionDiscoveryTests(unittest.TestCase):
    def test_parse_worktree_list_uses_embedded_heads(self):
        value=('worktree /repo/main\0HEAD '+'a'*40+'\0branch refs/heads/main\0\0'
               'worktree /repo/feature\0HEAD '+'b'*40+'\0detached\0\0'
               'worktree /repo/prunable\0prunable\0\0')
        self.assertEqual(parse_worktree_heads(value),[('/repo/main','a'*40),('/repo/feature','b'*40)])

    def test_discovery_reuses_verified_ids_and_embedded_head_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'state';state.mkdir();repo=str(root/'repo');sha='c'*40
            write_json(state/'watch-cursors.json',{repo:sha})
            porcelain=f'worktree {repo}\0HEAD {sha}\0branch refs/heads/main\0\0'
            with patch('src.benchmark_sync.submission.git',return_value=porcelain.encode()) as git_call, \
                 patch('src.benchmark_sync.submission.unpack',side_effect=AssertionError('should use the verified ID cache')):
                self.assertEqual(discover(state,[repo],'member',known_record_ids={'f'*64}),[])
            git_call.assert_called_once_with(repo,'worktree','list','--porcelain','-z')


if __name__=='__main__': unittest.main()
