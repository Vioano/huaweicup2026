import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.benchmark_sync.engine import write_json
from src.benchmark_sync.submission import discover, parse_worktree_heads


class SubmissionDiscoveryTests(unittest.TestCase):
    @staticmethod
    def commit(repo, message):
        subprocess.run(['git','-C',str(repo),'add','-A'],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['git','-C',str(repo),'commit','-q','-m',message],check=True)

    @staticmethod
    def feed(path, value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'schema_version':1,'records':[
            {'provenance':{'producer_session':'member/s-test'},'value':value}]}))

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

    def test_changed_tree_scans_only_new_and_modified_feeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();state=root/'state';state.mkdir()
            subprocess.run(['git','-C',str(repo),'init','-q'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.name','Test'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.email','test@example.invalid'],check=True)
            old=repo/'results/old/board-feed-old.json'
            changed=repo/'results/changed/board-feed-changed.json'
            self.feed(old,1);self.feed(changed,2)
            self.commit(repo,'first feeds')
            with patch('src.benchmark_sync.submission.enqueue') as enqueue_call:
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            self.assertEqual({call.args[3] for call in enqueue_call.call_args_list},
                             {'results/old/board-feed-old.json','results/changed/board-feed-changed.json'})
            unchanged=repo/'results/unchanged/board-feed-unchanged.json'
            self.feed(unchanged,3);self.commit(repo,'another old feed')
            with patch('src.benchmark_sync.submission.enqueue'):
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            # Deleting an old feed is not an error or a request to resend it.
            old.unlink();self.feed(changed,4)
            new=repo/'results/new/board-feed-new.json';self.feed(new,5)
            self.commit(repo,'new and changed feeds')
            with patch('src.benchmark_sync.submission.enqueue') as enqueue_call:
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            self.assertEqual({call.args[3] for call in enqueue_call.call_args_list},
                             {'results/changed/board-feed-changed.json','results/new/board-feed-new.json'})
            self.assertEqual(len(enqueue_call.call_args_list),2)
            # A pruned or stale cursor must rescan the reachable tree, not lose
            # batches while attempting a diff against a nonexistent object.
            write_json(state/'watch-cursors.json',{str(repo.resolve()):'0'*40})
            with patch('src.benchmark_sync.submission.enqueue') as enqueue_call:
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            self.assertEqual({call.args[3] for call in enqueue_call.call_args_list},
                             {'results/changed/board-feed-changed.json',
                              'results/new/board-feed-new.json',
                              'results/unchanged/board-feed-unchanged.json'})

    def test_failed_changed_feed_is_retried_without_advancing_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();state=root/'state';state.mkdir()
            subprocess.run(['git','-C',str(repo),'init','-q'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.name','Test'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.email','test@example.invalid'],check=True)
            self.feed(repo/'results/board-feed-first.json',1)
            self.commit(repo,'first')
            with patch('src.benchmark_sync.submission.enqueue'):
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            cursor_key=str(repo.resolve())
            first=json.loads((state/'watch-cursors.json').read_text())[cursor_key]
            self.feed(repo/'results/board-feed-second.json',2)
            self.commit(repo,'second')
            with patch('src.benchmark_sync.submission.enqueue',side_effect=ValueError('retry me')):
                errors=discover(state,[str(repo)],'member',known_record_ids=set())
            self.assertEqual(len(errors),1)
            self.assertEqual(json.loads((state/'watch-cursors.json').read_text())[cursor_key],first)
            with patch('src.benchmark_sync.submission.enqueue') as enqueue_call:
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            self.assertEqual(enqueue_call.call_count,1)
            self.assertEqual(enqueue_call.call_args.args[3],'results/board-feed-second.json')

    def test_symlink_to_regular_type_change_is_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();state=root/'state';state.mkdir()
            subprocess.run(['git','-C',str(repo),'init','-q'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.name','Test'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.email','test@example.invalid'],check=True)
            path=repo/'results/board-feed-type.json'
            path.parent.mkdir(parents=True)
            path.symlink_to('missing-target.json')
            self.commit(repo,'old symlink')
            # An older watcher could skip this type change and advance a cursor
            # at a symlink tree. The next regular feed must still be discovered.
            symlink_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            write_json(state/'watch-cursors.json',{str(repo.resolve()):symlink_head})
            path.unlink();self.feed(path,1)
            self.commit(repo,'new regular feed')
            with patch('src.benchmark_sync.submission.enqueue') as enqueue_call:
                self.assertEqual(discover(state,[str(repo)],'member',known_record_ids=set()),[])
            self.assertEqual(enqueue_call.call_count,1)
            self.assertEqual(enqueue_call.call_args.args[3],'results/board-feed-type.json')


if __name__=='__main__': unittest.main()
