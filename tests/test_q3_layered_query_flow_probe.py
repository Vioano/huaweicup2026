"""Pure admission and gate checks; never invokes official scoring."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from src.q3.feedback_benchmark import digest, read
from src.q3.layered_query_flow_probe import CONFIG, GRAPH, ROOT, decide, old_control


CONTROL = ROOT / 'results/a/q3-nikolastarx/layered-one-shot-20260925/control/control.json'


def validate(path=CONTROL, sha=None):
    return old_control(path, sha or digest(path), graph_sha256=digest(GRAPH),
                       config_sha256=digest(CONFIG),
                       official_code_sha256=read(CONTROL)['identity']['official_sha256'])


class ProbePureTests(unittest.TestCase):
    def test_archived_control_three_originals_and_pair(self):
        old = validate()
        self.assertEqual((old['M3'], old['M2']), (30642, 37327))

    def test_control_hash_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
            validate(sha='0' * 64)

    def test_p2_gate_requires_strict_p3_improvement(self):
        old = {'M3': 30642, 'M2': 37327}
        self.assertFalse(decide(30642, None, old)['run_p2'])
        self.assertTrue(decide(30641, None, old)['run_p2'])

    def test_acceptance_uses_exact_ratio_and_m2_nonregression(self):
        old = {'M3': 30642, 'M2': 37327}
        self.assertFalse(decide(30000, 36000, old)['accepted'])
        self.assertFalse(decide(30000, 37328, old)['accepted'])
        self.assertTrue(decide(30000, 37000, old)['accepted'])

    def test_same_plan_pair_guard_rejects_tampered_control(self):
        control = deepcopy(read(CONTROL))
        control['pair_evidence']['plan_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'control.json'
            path.write_text(json.dumps(control))
            with self.assertRaisesRegex(ValueError, 'same-plan'):
                validate(path)


if __name__ == '__main__':
    unittest.main()
