import copy
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/benchmark_board'))
from core import digest, packed
from mirror import MirrorView
from app import make_handler
from benchmark_sync.snapshot import read_central, publish_files, canonical
import test_ledger


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_ledger.LedgerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.source['repo'] = 'example/project'
        self.root = Path(self.fixture.temp.name)
        self.directory = self.root / 'mirror'
        self.current = self.directory / 'current.json'
        self.fixture.put(self.fixture.record())
        self.payload = self.export()
        publish_files(self.payload, self.directory)

    def export(self):
        return read_central(self.root / 'ledger.sqlite3', frozen_manifest=self.fixture.man,
                            algorithms={'algorithms': []}, code_commit='1' * 40)

    def view(self):
        return MirrorView(self.current, self.fixture.man)

    def force_candidate(self, candidate):
        # Simulate a transport installation; deliberately bypass its history guard
        # to verify that the reader also refuses to replace a valid visible view.
        candidate['record_count'] = len(candidate['records'])
        candidate['record_ids_sha256'] = digest(('\n'.join(sorted(r['id'] for r in candidate['records'])) + '\n').encode())
        candidate['records_sha256'] = digest(canonical(candidate['records']))
        candidate['snapshot_id'] = digest(canonical(candidate))
        with tempfile.TemporaryDirectory() as tmp:
            manifest = publish_files(candidate, Path(tmp))
            shutil.copy2(Path(tmp) / manifest['payload_file'], self.directory)
            shutil.copy2(Path(tmp) / 'current.json', self.current)

    def test_full_history_and_selection_parity(self):
        f = self.fixture
        lower = f.record('better', 80)
        report = f.record('report', 1)
        report['algorithm_id'] = 'reports'
        report['artifacts'] = {}
        f.put(lower, report)
        lower.update(revision=2, status='withdrawn')
        f.put(lower)
        publish_files(self.export(), self.directory)
        view = self.view()
        self.assertEqual(view.records(), f.l.records())
        for algorithm, run, preview in [(None, None, False), (None, None, True),
                                         ('fixture', 'synthetic-test-only', False), ('reports', None, True)]:
            direct = f.l.snapshot(algorithm, run, preview)
            mirrored = view.snapshot(algorithm, run, preview)
            self.assertEqual(direct['cells'], mirrored['cells'])
            self.assertEqual(direct['record_count'], mirrored['record_count'])
        self.assertEqual(view.events(1)[0]['cursor'], 2)
        self.assertFalse((self.directory / 'ledger.sqlite3').exists())
        self.assertFalse((self.directory / 'blobs').exists())
        self.assertFalse(view.health()['runtime']['local_artifacts_verified'])

    def test_atomic_valid_upgrade_and_broken_update_retains_view(self):
        view = self.view()
        self.fixture.put(self.fixture.record('new', 70))
        publish_files(self.export(), self.directory)
        self.assertEqual(len(view.records()), 2)
        good_manifest = self.current.read_bytes()
        self.current.write_text('{broken', encoding='utf-8')
        self.assertEqual(len(view.records()), 2)
        self.assertEqual(view.health()['status'], 'degraded')
        self.current.write_bytes(good_manifest)
        self.assertEqual(view.health()['status'], 'ok')

    def test_regressions_and_rewrites_never_replace_view(self):
        view = self.view()
        self.fixture.put(self.fixture.record('new', 70))
        upgraded = self.export()
        publish_files(upgraded, self.directory)
        self.assertEqual(len(view.records()), 2)
        for kind in ('rollback', 'drop', 'rewrite'):
            with self.subTest(kind=kind):
                candidate = copy.deepcopy(upgraded)
                if kind == 'rollback': candidate['sequence'] -= 1
                if kind == 'drop': candidate['records'] = candidate['records'][1:]
                if kind == 'rewrite': candidate['records'][0]['algorithm_name'] = 'rewritten'
                self.force_candidate(candidate)
                self.assertEqual(view.records(), upgraded['records'])
                self.assertEqual(view.health()['status'], 'degraded')

    def test_bad_initial_payload_and_frozen_identity_fail_closed(self):
        manifest = json.loads(self.current.read_text())
        payload = self.directory / manifest['payload_file']
        good = payload.read_bytes()
        payload.write_bytes(b'incomplete')
        with self.assertRaises(ValueError): self.view()
        payload.write_bytes(good)
        frozen = copy.deepcopy(self.fixture.man)
        frozen['official_code_hash'] = 'f' * 64
        with self.assertRaises(ValueError): MirrorView(self.current, frozen)

    def test_read_only_http_contract_and_original_links(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.view()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:' + str(server.server_port)
        def get(path):
            with urlopen(url + path) as response: return json.load(response)
        self.assertEqual(get('/api/v1/health')['mode'], 'central_mirror')
        self.assertEqual(get('/api/v1/records?limit=1')['total'], 1)
        self.assertEqual(get('/api/v1/catalog'), {'algorithms': []})
        self.assertEqual(len(get('/api/v1/cells?problem=P3&case_id=002&cores=4')['cells']), 1)
        key = self.payload['records'][0]['artifacts']['plan']['sha256']
        with self.assertRaises(HTTPError) as caught: get('/api/v1/blobs/' + key)
        self.assertEqual(caught.exception.code, 409)
        self.assertTrue(json.load(caught.exception)['sources'][0].startswith('https://github.com/example/project/blob/'))
        caught.exception.close()
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(url + '/api/v1/records', data=b'{}'))
        self.assertEqual(caught.exception.code, 405)
        caught.exception.close()


if __name__ == '__main__': unittest.main()
