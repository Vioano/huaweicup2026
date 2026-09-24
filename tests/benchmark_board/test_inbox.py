import json
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/benchmark_board'))
from core import packed
from app import start_ingest_workers
from inbox import consume, drain_inbox, REPO
from protocol import ROOT
import test_ledger


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_ledger.LedgerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = Path(self.fixture.temp.name) / 'inbox'
        self.delivery = self.root / 'delivery-1'
        self.delivery.mkdir(parents=True)
        self.feed = json.loads((ROOT / 'docs/benchmarks/examples/submission-v1.json').read_text(encoding='utf-8'))
        self.feed['records'][0].update(self.fixture.record())
        self.feed['records'][0]['metrics'].update(solver_wall_seconds=None, evaluation_wall_seconds=None)
        self.request = {'schema_version': 1, 'id': 'delivery-1', 'feed_file': 'feed.json',
                        'source': {'id': 'auto:member:delivery-1', 'commit': 'd' * 40,
                                   'feed': 'results/feed.json',
                                   'url': f'https://github.com/{REPO}/blob/{"d" * 40}/results/feed.json'}}
        for path, data in self.fixture.blobs.items():
            target = self.delivery / 'artifacts' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.write()

    def write(self):
        (self.delivery / 'request.json').write_text(packed(self.request), encoding='utf-8')
        (self.delivery / 'feed.json').write_text(packed(self.feed), encoding='utf-8')

    def test_admission_result_and_crash_before_receipt_retry_are_idempotent(self):
        result = consume(self.fixture.l, self.delivery)
        self.assertEqual(result['state'], 'accepted')
        self.assertEqual(result['receipt']['added'], 1)
        self.assertEqual(result['admission']['eligible'], 1)
        self.assertEqual(drain_inbox(self.fixture.l, self.root), [])
        # Lost receipt after an already committed batch, as in a process crash.
        (self.delivery / 'result.json').unlink()
        retried = consume(self.fixture.l, self.delivery)
        self.assertEqual(retried['receipt']['added'], 0)
        self.assertTrue(retried['receipt']['duplicate'])
        self.assertEqual(len(self.fixture.l.records()), 1)
        self.assertEqual(len(self.fixture.l.events(0)), 1)

    def test_transport_incomplete_artifact_is_terminal_rejection_not_report(self):
        path = self.feed['records'][0]['artifacts']['result']['path']
        (self.delivery / 'artifacts' / path).unlink()
        response = drain_inbox(self.fixture.l, self.root)[0]
        self.assertEqual(response['state'], 'rejected')
        self.assertEqual(self.fixture.l.records(), [])
        (self.delivery / 'artifacts' / path).write_bytes(self.fixture.blobs[path])
        self.assertEqual(drain_inbox(self.fixture.l, self.root), [])

    def test_malformed_request_or_variable_source_never_ingested(self):
        for bad in ([], None, dict(self.request, id='different'),
                    dict(self.request, source=dict(self.request['source'], url='https://github.com/example/main'))):
            with self.subTest(request=bad):
                (self.delivery / 'request.json').write_text(packed(bad), encoding='utf-8')
                result = consume(self.fixture.l, self.delivery)
                self.assertEqual(result['state'], 'rejected')
                (self.delivery / 'result.json').unlink()
        self.assertEqual(self.fixture.l.records(), [])

    def test_escaping_artifact_symlink_rejected_and_unpublished_directory_ignored(self):
        path = self.feed['records'][0]['artifacts']['plan']['path']
        target = self.delivery / 'artifacts' / path
        outside = Path(self.fixture.temp.name) / 'outside.json'
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
        result = consume(self.fixture.l, self.delivery)
        self.assertEqual(result['state'], 'rejected')
        self.assertIn('escapes', result['error'])
        (self.root / 'unfinished').mkdir()
        self.assertEqual(drain_inbox(self.fixture.l, self.root), [])

    def test_cli_receives_with_legacy_git_sync_disabled(self):
        state = self.root.parent / 'isolated-cli-ledger'
        process = subprocess.Popen([sys.executable, str(ROOT / 'src/benchmark_board/app.py'),
                                    '--state', str(state), 'serve', '--port', '0', '--no-sync',
                                    '--sync-inbox', str(self.root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            result_file = self.delivery / 'result.json'
            deadline = time.monotonic() + 8
            while not result_file.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(result_file.exists())
            result = json.loads(result_file.read_bytes())
            self.assertEqual(result['state'], 'accepted')
            self.assertEqual(result['receipt']['added'], 1)
            # The CLI uses the real frozen manifest, so this synthetic fixture
            # must remain a report. Nothing is copied into the production state.
            self.assertEqual(result['admission']['eligible'], 0)
        finally:
            process.terminate()
            process.communicate(timeout=5)

    def test_completed_delivery_does_not_wait_for_slow_git_poll(self):
        (self.delivery / 'request.json').unlink()
        entered = threading.Event()
        release = threading.Event()
        stop = threading.Event()
        def slow_git(repo, *args, **kwargs):
            if args[0] == 'ls-remote':
                entered.set()
                release.wait(timeout=5)
                return b''
            self.fail('Unexpected Git command during blocked source poll')
        source = {'id': 'slow-source', 'ref': 'codex/slow-source', 'prefix': 'results/slow-source'}
        with patch('app.git', side_effect=slow_git):
            workers = start_ingest_workers(self.fixture.l, ROOT, [source], self.root,
                                           sync_enabled=True, stop=stop)
            try:
                self.assertTrue(entered.wait(timeout=2))
                self.write()  # Publish the complete request while Git is blocked.
                result_file = self.delivery / 'result.json'
                deadline = time.monotonic() + 2
                while not result_file.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(result_file.exists(), 'Local delivery waited for remote Git')
                self.assertFalse(release.is_set())
                self.assertEqual(json.loads(result_file.read_text())['state'], 'accepted')
                self.assertEqual(len(self.fixture.l.records()), 1)
            finally:
                release.set()
                stop.set()
                for worker in workers: worker.join(timeout=2)


if __name__ == '__main__': unittest.main()
