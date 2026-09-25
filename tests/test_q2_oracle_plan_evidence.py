"""Ensure the exact scored candidate survives failure before/after dispatch."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from src.q2_nikolastarx.adaptive_guarded import score_adapter

class PlanEvidenceTests(unittest.TestCase):
    def ledger(self):
        return {'calls': {'E2_api_attempted': 0, 'E0_fallback': 0, 'native_returns': 0},
                'request_in_flight': False, 'attempts': []}

    def test_input_saved_before_dispatch_and_retained_on_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'solver.json'; ledger=self.ledger()
            plan={'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
            def failing_oracle(actual):
                persisted=json.loads(path.read_text())
                attempt=persisted['attempts'][0]
                raw=(path.parent/attempt['plan_file']).read_bytes()
                self.assertEqual(json.loads(raw), actual)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), attempt['plan_sha256'])
                self.assertTrue(persisted['request_in_flight'])
                raise RuntimeError('uncertain native transport')
            oracle=score_adapter(failing_oracle,ledger,path)
            with self.assertRaisesRegex(RuntimeError,'uncertain native transport'):oracle(plan)
            self.assertEqual(ledger['calls']['E2_api_attempted'],1)
            self.assertTrue(ledger['request_in_flight'])
            self.assertTrue((path.parent/'oracle-plans/001.json').is_file())
            with self.assertRaisesRegex(RuntimeError,'uncertain E2'):oracle(plan)
            self.assertEqual(ledger['calls']['E2_api_attempted'],1)

    def test_existing_artifact_blocks_dispatch_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'solver.json'; ledger=self.ledger()
            target=path.parent/'oracle-plans/001.json';target.parent.mkdir();target.write_bytes(b'previous')
            calls=[]
            oracle=score_adapter(lambda p:calls.append(p),ledger,path)
            with self.assertRaises(FileExistsError):oracle({'test':1})
            self.assertEqual(calls,[]); self.assertEqual(ledger['calls']['E2_api_attempted'],0)
            self.assertEqual(target.read_bytes(),b'previous')

if __name__=='__main__':unittest.main()
