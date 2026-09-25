"""Fake-only edge and final replay tests; no official compiler or response calls."""
import unittest
from unittest.mock import patch
import hashlib
import json
from pathlib import Path
import tempfile

from src.review import p1_lazy_memory_probe as probe
from src.review.p1_lazy_memory_probe import charge, verify_final, BoundedKernel
from src.review.p1_lazy_packet_search import UnknownResult
from src.q1.response_compile import UnsupportedResponse


class Task:
    def signature(self): return ('task',)


class FakeKernel:
    compiles = 0
    completed = 0
    response_attempts = response_completed = 0
    limit = 10
    full_reserved = 0
    full_confirmed = 0
    def check(self): pass
    def response(self, lines): return {'makespan': 8}


class LazyMemoryProbeTests(unittest.TestCase):
    def test_partial_compile_accounting_is_unknown_with_known_lower_bound(self):
        kernel = FakeKernel()
        kernel.compiles, kernel.completed = 3, 1
        counts = probe.accounting(kernel)
        self.assertIsNone(counts['task_compile_confirmed_completed'])
        self.assertEqual(counts['task_compile_confirmed_lower_bound'], 1)
        kernel.full_confirmed = 2
        self.assertEqual(probe.accounting(kernel)['task_compile_confirmed_completed'], 3)

    def test_publication_requires_receipt_before_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            report = {'status': 'verified_model'}
            probe.publish(output, report, {'core_schedules': [[]]})
            receipt = json.loads((output/'report.json').read_text())
            self.assertEqual(receipt['plan_sha256'], hashlib.sha256((output/'plan.json').read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            replace = Path.replace
            def interrupted(path, target):
                if path.name == 'report.json.tmp':
                    raise OSError('simulated receipt publication failure')
                return replace(path, target)
            with patch.object(Path, 'replace', interrupted), self.assertRaises(OSError):
                probe.publish(output, {'status': 'verified_model'}, {'core_schedules': [[]]})
            self.assertFalse((output/'plan.json').exists())
            self.assertFalse(list(output.glob('*.tmp')))

    def test_cli_unknown_exits_nonzero_without_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, output = Path(tmp)/'graph.json', Path(tmp)/'output'
            graph.write_text('{}')
            argv = ['probe', str(graph), '--execute', '--output-root', str(output),
                    '--cores', '1', '--capacity-l1', '1', '--capacity-ub', '1',
                    '--bandwidth', '60', '--gate', '100', '--task-limit', '2',
                    '--final-max-tasks', '1', '--response-limit', '2', '--oracle-limit', '1',
                    '--expansion-limit', '1', '--seconds', '1']
            with patch('sys.argv', argv), patch.object(probe, 'hashes', return_value={}), \
                 patch.object(probe, 'source_scope', return_value=()), \
                 patch.object(probe, 'construct', side_effect=UnknownResult('fake budget stop')), \
                 patch.object(probe.signal, 'getitimer', return_value=(0, 0)), \
                 patch.object(probe.signal, 'signal'), patch.object(probe.signal, 'setitimer'), \
                 self.assertRaises(SystemExit) as raised:
                probe.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse((output/'plan.json').exists())
            self.assertEqual(json.loads((output/'report.json').read_text())['status'], 'unknown')

    def test_gate_conventions(self):
        self.assertEqual(charge('normal', 0, True, 8, 100), 8)
        self.assertEqual(charge('normal', 1, True, 8, 100), 108)
        self.assertEqual(charge('drain', 1, True, 8, 100), 108)
        self.assertEqual(charge('terminal', 0, True, 8, 100), 8)
        self.assertEqual(charge('terminal', 0, False, 0, 100), 0)

    def test_budget_unknown_before_fake_compile(self):
        calls = []
        kernel = FakeKernel()
        with self.assertRaises(UnknownResult):
            verify_final({}, {'core_schedules': [[0]]}, [[('task',)]], 3, 8,
                         kernel, {}, 60, 0,
                         compiler=lambda *args: calls.append(1), validator=lambda *args: None)
        self.assertEqual(calls, [])
        bounded = BoundedKernel(object(), 100, 1, 0, float('inf'))
        with self.assertRaises(UnknownResult):
            bounded.response([[Task()]])
        self.assertEqual(bounded.response_attempts, 0)
        bounded.response_limit = 1
        with patch.object(probe, 'simulate', side_effect=RuntimeError('response event budget exhausted')):
            with self.assertRaises(UnknownResult):
                bounded.response([[Task()]])
        self.assertEqual((bounded.response_attempts, bounded.response_completed), (1, 0))

    def test_final_signature_and_bytes_mismatch_never_verify(self):
        plan = {'core_schedules': [[0]]}
        def compiler(*args):
            return [[Task()]], {'traffic': {'scheduled_copy_bytes': 3}}
        with self.assertRaisesRegex(UnsupportedResponse, 'signatures'):
            verify_final({}, plan, [[('wrong',)]], 3, 8, FakeKernel(), {}, 60, 2,
                         compiler=compiler, validator=lambda *args: None)
        with self.assertRaisesRegex(UnsupportedResponse, 'DDR bytes'):
            verify_final({}, plan, [[('task',)]], 4, 8, FakeKernel(), {}, 60, 2,
                         compiler=compiler, validator=lambda *args: None)
        with self.assertRaisesRegex(UnsupportedResponse, 'scalar response'):
            verify_final({}, plan, [[('task',)]], 3, 9, FakeKernel(), {}, 60, 2,
                         compiler=compiler, validator=lambda *args: None)

    def test_nonoptimal_scalar_candidate_still_replays_original_id_plan(self):
        class Family:
            B = 1
            cores = 1
        class Kernel(FakeKernel):
            def __init__(self, *args):
                self.tasks = {(1, 2): {'task': Task(), 'bytes': 3}}
                self.compiles = self.completed = self.full_confirmed = 0
                self.response_attempts = 0
                self.deadline = float('inf')
            def profile(self, *args, **kwargs):
                return {'cost': 8, 'groups': [[1, 2]], 'bytes': 3}
            def suffix(self, *args):
                return {'cost': 0, 'groups': [[]], 'bytes': 0}
        class Resource:
            counts = (1,)
            a = b = c = d_whole = d_return = 1
            def __init__(self, **kwargs): pass
            def box(self, *args, **kwargs): return {'frontier_lower_bound': 0}
        def fake_search(B, exact, bound, budget, **kwargs):
            self.assertEqual(budget, 0)  # both seed queries use the total budget
            self.assertEqual(kwargs['incumbent'][0], 8)
            self.assertEqual(exact('normal', (0, 0), (1, 0)), 8)
            self.assertEqual(exact('terminal', (1, 0), 'merge'), 0)
            return {'best_path': (('normal', (0, 0), (1, 0)),
                                  ('terminal', (1, 0), 'merge')),
                    'upper': 8, 'lower': 0, 'optimal': False,
                    'open_items': [{'kind': 'box'}]}
        def fake_final(graph, plan, expected, bytes_, upper, *args):
            self.assertEqual((expected, bytes_, upper), ([[('task',)]], 3, 8))
            return {'traffic': {'scheduled_copy_bytes': 3}}
        with patch.object(probe, 'guard'), patch.object(probe, 'graph_resources', return_value={}), \
             patch.object(probe, 'choose_return_seed', return_value={'s': 0}), \
             patch.object(probe, 'Resources', Resource), patch.object(probe, 'search', fake_search), \
             patch.object(probe, 'verify_final', fake_final):
            state = {}
            plan, report = probe.construct({'ops': [{'id': 1, 'op': 'PIPE_V'},
                                                     {'id': 2, 'op': 'PIPE_M'}]},
                                           1, {'L1': 1, 'UB': 1}, 60, 100,
                                           task_limit=5, final_max_tasks=2,
                                           response_limit=2, oracle_limit=2,
                                           expansion_limit=2, seconds=1,
                                           family_factory=lambda *args: Family(),
                                           kernel_factory=Kernel, state=state)
        self.assertEqual(plan['node_to_subgraph'], {'1': 0, '2': 0})
        self.assertFalse(report['scalar']['optimal'])
        self.assertEqual(state['scalar']['open_items'], [{'kind': 'box'}])

    def test_unknown_seed_is_not_incumbent_or_retried(self):
        class Family:
            B = cores = 1
        class Kernel(FakeKernel):
            def __init__(self, *args):
                self.profile_calls = 0
                self.deadline = float('inf')
            def profile(self, *args, **kwargs):
                self.profile_calls += 1
                raise UnknownResult('fake incomplete compilation')
        def fake_search(B, exact, bound, budget, **kwargs):
            self.assertEqual(budget, 1)
            self.assertIsNone(kwargs['incumbent'])
            self.assertIs(exact('normal', (0, 0), (1, 0)), probe.Unknown)
            return {'best_path': None, 'upper': None, 'lower': 0, 'optimal': False}
        with patch.object(probe, 'guard'), patch.object(probe, 'graph_resources', return_value={}), \
             patch.object(probe, 'Resources'), \
             patch.object(probe, 'choose_return_seed', return_value={'s': 0}), \
             patch.object(probe, 'search', fake_search):
            state = {}
            with self.assertRaises(UnknownResult):
                probe.construct({}, 1, {'L1': 1, 'UB': 1}, 60, 100,
                                task_limit=5, final_max_tasks=2, response_limit=2,
                                oracle_limit=2, expansion_limit=2, seconds=1,
                                family_factory=lambda *args: Family(),
                                kernel_factory=Kernel, state=state)
        self.assertEqual(state['kernel'].profile_calls, 1)
        self.assertEqual(state['seed']['status'], 'unknown')


if __name__ == '__main__': unittest.main()
