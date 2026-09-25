"""Pure unit tests; never import or call the official evaluator."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from src.q3 import r9f_one_shot as probe


class R9FOneShotTests(TestCase):
    def test_saved_control_reads_real_board_blob_bytes(self):
        path = (probe.ROOT / 'results/a/q3-nikolastarx/r9f-one-shot-20260926/'
                'old_control.json')
        old = probe.old_control(
            path, 'fc3ccd32cb89398fcf35b8d6d622e2e9336ab026fdc8fff8f0cac07054777d38',
            graph_sha256='dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d',
            config_sha256='dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9',
            official_code_sha256='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0')
        self.assertEqual((old['M3'], old['M2']), (116345, 131631))
        self.assertEqual(old['plan_sha256'],
                         '955cfb794f0c82641b6d4c1411591c77dafc0458a2c1731184fee809aef16ff1')

    def test_fixed_plan_identity(self):
        self.assertEqual(probe.digest(probe.FIXED_PLAN), probe.PLAN_SHA256)
        plan = probe.read(probe.FIXED_PLAN)
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(len(plan['core_schedules']), 5)

    def test_p2_gate_and_exact_ratio(self):
        old = {'M3': 100, 'M2': 120}
        self.assertFalse(probe.decide(100, None, old)['run_p2'])
        self.assertTrue(probe.decide(99, None, old)['run_p2'])
        self.assertFalse(probe.decide(99, 121, old)['accepted'])
        self.assertFalse(probe.decide(99, 118, old)['accepted'])
        self.assertTrue(probe.decide(99, 119, old)['accepted'])

    def _run_main(self, *, p3=90, p2=110, fail_p3=False):
        with TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            candidate = base / 'candidate'
            candidate.mkdir()
            (candidate / 'case_068_multicore_res.json').write_bytes(probe.FIXED_PLAN.read_bytes())
            admission = base / 'admission.json'
            admission.write_text('{}')
            output = base / 'new-output'
            source_sha = probe.digest(Path(probe.__file__))
            argv = ['r9f_one_shot', str(candidate), str(output), '--source', 'a' * 40,
                    '--source-sha256', source_sha, '--plan-sha256', probe.PLAN_SHA256,
                    '--admission-file', str(admission), '--admission-sha256', probe.digest(admission),
                    '--control', str(base / 'control.json'), '--control-sha256', 'b' * 64]
            calls = []

            def fake_phase(args, phase, deadline, report):
                calls.append(phase)
                if phase == 'p3':
                    if fail_p3:
                        raise RuntimeError('first anomaly')
                    probe.write(output / 'p3.worker.json', {'guard': {'status': 'passed'}})
                    return {'makespan': p3}
                return {'makespan': p2}

            with (patch.object(probe, 'BASE', base),
                  patch.object(probe, 'verify_source', return_value=('official-sha', {})),
                  patch.object(probe, 'old_control', return_value={'M3': 100, 'M2': 120}),
                  patch.object(probe, 'run_phase', side_effect=fake_phase),
                  patch.object(probe.sys, 'argv', argv)):
                if fail_p3:
                    with self.assertRaisesRegex(RuntimeError, 'first anomaly'):
                        probe.main()
                else:
                    probe.main()
            return calls, json.loads((output / 'run.json').read_text())

    def test_only_improving_p3_opens_single_p2(self):
        calls, report = self._run_main(p3=99, p2=119)
        self.assertEqual(calls, ['p3', 'p2'])
        self.assertTrue(report['accepted'])
        self.assertEqual(report['budget']['retries'], 0)
        calls, report = self._run_main(p3=100)
        self.assertEqual(calls, ['p3'])
        self.assertFalse(report['accepted'])

    def test_first_anomaly_stops_before_p2(self):
        calls, report = self._run_main(fail_p3=True)
        self.assertEqual(calls, ['p3'])
        self.assertEqual(report['status'], 'failed')

    def test_mismatched_source_fails_before_any_phase(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            candidate = base / 'candidate'
            candidate.mkdir()
            (candidate / 'case_068_multicore_res.json').write_bytes(probe.FIXED_PLAN.read_bytes())
            argv = ['r9f_one_shot', str(candidate), str(base / 'output'), '--source', 'a' * 40,
                    '--source-sha256', '0' * 64, '--plan-sha256', probe.PLAN_SHA256]
            with patch.object(probe, 'BASE', base), patch.object(probe.sys, 'argv', argv), \
                    patch.object(probe, 'verify_source') as verify:
                with self.assertRaisesRegex(ValueError, 'runner source SHA-256 differs'):
                    probe.main()
                verify.assert_not_called()
            self.assertFalse((base / 'output').exists())

    def test_worker_rejects_unreserved_call_before_official_import(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            candidate = base / 'candidate'
            output = base / 'output'
            candidate.mkdir()
            output.mkdir()
            (candidate / 'case_068_multicore_res.json').write_bytes(probe.FIXED_PLAN.read_bytes())
            admission = base / 'admission.json'
            admission.write_text('{}')
            args = SimpleNamespace(candidate=candidate, output=output,
                                   source='a' * 40, plan_sha256=probe.PLAN_SHA256,
                                   admission_file=admission,
                                   admission_sha256=probe.digest(admission),
                                   source_sha256=probe.digest(Path(probe.__file__)), worker='p3')
            with patch.object(probe, 'BASE', base), \
                    patch.object(probe, 'verify_source', return_value=('official-sha', {})):
                with self.assertRaisesRegex(FileNotFoundError, 'reservation'):
                    probe.worker(args)
            self.assertFalse((output / 'p3.claim.json').exists())
