import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/benchmark_board'))
from protocol import validate_feed, ROOT
import test_ledger


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.feed = json.loads((ROOT/'docs/benchmarks/examples/submission-v1.json').read_text())
        self.row = self.feed['records'][0]

    def test_complete_template_and_legacy_real_feed(self):
        self.assertTrue(validate_feed(self.feed))
        old = json.loads((ROOT/'results/benchmark-board/feeds/board-feed-initial-20260924.json').read_text())
        self.assertFalse(validate_feed(old))

    def test_incomplete_metadata_rejected(self):
        del self.row['provenance']['runner']
        with self.assertRaisesRegex(ValueError, 'runner'):
            validate_feed(self.feed)

    def test_unknowns_need_reasons(self):
        self.row['provenance']['missing_reasons'] = {}
        with self.assertRaisesRegex(ValueError, 'missing_reasons'):
            validate_feed(self.feed)

    def test_source_cannot_use_export_head(self):
        self.row['solver_commit'] = 'a'*40
        self.row['provenance']['solver']['source'] = {'repo':'a/b','commit':'b'*40,'path':'src/solver.py','entrypoint':'main'}
        with self.assertRaisesRegex(ValueError, 'differs'):
            validate_feed(self.feed)

    def test_duplicate_identity_and_invalid_numbers(self):
        self.feed['records'].append(copy.deepcopy(self.row))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate_feed(self.feed)
        self.feed['records'].pop()
        for bad in [True, -1, float('nan'), '0.1']:
            self.row['metrics']['solver_wall_seconds'] = bad
            with self.assertRaises(ValueError):
                validate_feed(self.feed)

    def test_failed_submission_preserves_reason_not_final_result(self):
        self.row['status'] = 'timeout'
        with self.assertRaisesRegex(ValueError, 'failure'):
            validate_feed(self.feed)
        self.row['provenance']['measurement']['failure'] = {'stage':'solver','reason':'budget reached','exit_code':124,'elapsed_seconds':10}
        self.row['metrics']['solver_wall_seconds'] = 10
        validate_feed(self.feed)
        self.row['metrics']['makespan_cycles'] = 99
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate_feed(self.feed)


class AdmissionTests(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    artifact = test_ledger.LedgerTests.artifact
    record = test_ledger.LedgerTests.record
    put = test_ledger.LedgerTests.put
    best = test_ledger.LedgerTests.best
    def test_failed_elapsed_time_retained(self):
        row = self.record()
        row['status'] = 'timeout'
        row['metrics']['solver_wall_seconds'] = 180.0
        self.put(row)
        self.assertIsNone(self.best())
        self.assertEqual(self.l.records()[0]['metrics']['solver_wall_seconds'], 180.0)

    def test_report_is_not_valid_and_wrong_identity_not_previewed(self):
        row = self.record()
        row['artifacts'] = {}
        self.put(row)
        cell = next(c for c in self.l.snapshot()['cells'] if c['attempts'])
        self.assertEqual(cell['status'], 'reported')
        row['revision'] = 2
        row['identity']['config_sha256'] = 'f'*64
        self.put(row)
        cell = next(c for c in self.l.snapshot(include_reported=True)['cells'] if c['attempts'])
        self.assertIsNone(cell['best'])

    def test_extra_movement_from_official_field(self):
        row = self.record()
        row['artifacts']['result'] = self.artifact('movement.json', {'scene':'B','problem':3,'cache_mode':'read_only','num_cores':4,'makespan':100,'data_movement_bytes':{'scheduled_copy_bytes':250,'added_copy_bytes':50}})
        self.put(row)
        self.assertEqual(self.best()['metrics']['extra_ddr_bytes'], 50)
        self.assertEqual(self.best()['metrics']['ddr_bytes'], 250)

if __name__ == '__main__':
    unittest.main()
