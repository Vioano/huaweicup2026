"""Six bounded, pure-Python checks for the saved partial-bucket compiler."""
from __future__ import annotations

from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SAVED = HERE.parent / 'pipeline-prefix-static-20260925'
spec = importlib.util.spec_from_file_location('partial_bucket_compile', HERE / 'compile.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


class SavedSnapshotChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((SAVED / 'case_044_multicore_res.json').read_text())
        with gzip.open(SAVED / 'snapshots.json.gz', 'rt') as stream:
            cls.snapshots = json.load(stream)
        cls.certificate = json.loads((SAVED / 'certificate.json').read_text())

    def compile(self, h, plan=None, snapshots=None):
        return compiler.compile_split(plan or self.plan, snapshots or self.snapshots,
                                      self.certificate, 2, h)

    def test_1_h10_matches_saved_example_and_preserves_inputs(self):
        before = deepcopy((self.plan, self.snapshots, self.certificate))
        candidate, words, facts = self.compile(10)
        self.assertEqual(candidate, json.loads((HERE / 'example-plan.json').read_text()))
        expected = json.loads((HERE / 'example-predicted-word.json').read_text())
        self.assertEqual(words['2'], expected['predicted_pre_step2_word'])
        self.assertEqual(facts['pilot_activation_positions'], [4, 5])
        self.assertEqual((self.plan, self.snapshots, self.certificate), before)

    def test_2_empty_head_or_tail_rejected(self):
        for h in (0, 17):
            with self.subTest(h=h), self.assertRaisesRegex(compiler.Reject, 'head_count'):
                self.compile(h)

    def test_3_tampered_saved_word_rejected(self):
        changed = deepcopy(self.snapshots)
        word = changed['candidate']['2']['pre_step2_word']
        word[0], word[1] = word[1], word[0]
        with self.assertRaisesRegex(compiler.Reject, 'baseline bucket reconstruction'):
            self.compile(10, snapshots=changed)

    def test_4_tampered_mapping_rejected(self):
        changed = deepcopy(self.plan)
        pilot_sg = changed['core_schedules'][2][0]
        pilot_op = next(int(u) for u, sg in changed['node_to_subgraph'].items()
                        if sg == pilot_sg)
        changed['node_to_subgraph'][str(pilot_op)] = changed['core_schedules'][2][1]
        with self.assertRaisesRegex(compiler.Reject, 'baseline bucket reconstruction'):
            self.compile(10, plan=changed)

    def test_5_h15_is_structural_and_global_dag(self):
        candidate, words, facts = self.compile(15)
        self.assertEqual(facts['head_prefix_cold_count'], 6)
        self.assertEqual(facts['pilot_activation_positions'], [6, 7])
        self.assertEqual(facts['global_pre_step2']['ops'], 1678)
        self.assertEqual(facts['interval_peaks'], {'L1': 516480, 'UB': 0})
        for core in ('0', '1', '3', '4'):
            self.assertEqual(words[core], self.snapshots['candidate'][core]['pre_step2_word'])
        self.assertEqual(len(candidate['node_to_subgraph']), len(self.plan['node_to_subgraph']))

    def test_6_duplicate_numeric_mapping_key_rejected(self):
        changed = deepcopy(self.plan)
        key = next(iter(changed['node_to_subgraph']))
        changed['node_to_subgraph']['00' + key] = changed['node_to_subgraph'][key]
        with self.assertRaisesRegex(compiler.Reject, 'canonical integer keys'):
            self.compile(10, plan=changed)



if __name__ == '__main__':
    unittest.main(verbosity=2)
