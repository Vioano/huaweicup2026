"""Static fifth-core checks against original frozen case bytes; no evaluator."""
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

from src.q3.fifth_core_contiguous import construct
from src.q3.layered_query_flow import GuardError, RawIndex


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / 'data/raw/a/official-cases.zip'
CONFIG = ROOT / 'data/raw/a/official/data/config.txt'


def configuration():
    result = {}
    section = None
    for line in CONFIG.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            section = line[1:-1]
            result[section] = {}
        else:
            key, value = line.split()
            result[section][key] = int(value)
    return result


def case(number):
    with zipfile.ZipFile(CASES) as archive:
        return json.loads(archive.read(f'data/case_{number:03d}.json'))


class FifthCoreContiguousTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = configuration()
        cls.capacity = cfg['capacity']
        cls.delay = cfg['multicore_scene_b']['cross_core_copy_delay_cycles']

    def check_structure(self, graph, plan, metadata, evidence):
        index = RawIndex.build(graph)
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        mapping = plan['node_to_subgraph']
        self.assertEqual(set(mapping), {str(u) for u in index.ops})
        self.assertEqual(set(mapping.values()), set(range(len(index.ops))))
        self.assertEqual(len(plan['core_schedules']), 5)
        slots = [subgraph for word in plan['core_schedules'] for subgraph in word]
        self.assertEqual(len(slots), len(index.ops))
        self.assertEqual(set(slots), set(mapping.values()))
        self.assertEqual(metadata['official_calls'], 0)
        self.assertIsNone(metadata['M3'])
        self.assertTrue(metadata['memory']['step2_no_spill_certificate'])
        for peaks in metadata['memory']['bucket_frontier_peaks']:
            for pool, limit in self.capacity.items():
                self.assertLessEqual(peaks[pool]['bytes'], limit)

        tau = evidence['global_tau']
        rank = {u: i for i, u in enumerate(tau)}
        self.assertEqual(set(tau), set(index.ops))
        for u in index.ops:
            for v in index.succ[u]:
                self.assertLess(rank[u], rank[v])
        owner = {int(u): c for u, c in evidence['owner'].items()}
        words = evidence['core_compute_words']
        self.assertEqual([len(word) for word in words], metadata['core_lengths'])
        for core, word in enumerate(words):
            self.assertTrue(all(owner[u] == core for u in word))
        shared = set(words[4])
        self.assertEqual(len(shared), metadata['shared_ops'])
        self.assertTrue(all(rank[u] < rank[v]
                            for u in shared for v in index.ops if v not in shared))
        ordered = metadata['ordered_components']
        self.assertEqual({u for part in ordered for u in part['nodes']}, shared)
        self.assertEqual(sum(len(part['nodes']) for part in ordered), len(shared))
        offset = 0
        for part in ordered:
            nodes = part['nodes']
            self.assertEqual(set(words[4][offset:offset + len(nodes)]), set(nodes))
            offset += len(nodes)

    def test_frozen_068_exact_plan_and_structure(self):
        graph = case(68)
        plan, metadata, evidence = construct(graph, 5, self.capacity, self.delay)
        digest = hashlib.sha256((json.dumps(plan, ensure_ascii=False, indent=2) + '\n').encode()).hexdigest()
        self.assertEqual(digest, 'ee8364e769437cb226cbe95cde845c0bbea59b2fd4e84dc47806d517949b323b')
        self.assertEqual(metadata['memory']['bucket_frontier_peaks'][4]['UB']['bytes'], 90112)
        self.check_structure(graph, plan, metadata, evidence)

    def test_088_same_static_rule_and_capacity_failure_is_closed(self):
        graph = case(88)
        plan, metadata, evidence = construct(graph, 5, self.capacity, self.delay)
        self.check_structure(graph, plan, metadata, evidence)
        self.assertEqual(metadata['shared_components'], 42)
        with self.assertRaisesRegex(GuardError, 'bucket-frontier capacity'):
            construct(graph, 5, {'L1': 1, 'UB': 1}, self.delay)

    def test_track_count_guard(self):
        with self.assertRaisesRegex(GuardError, 'K-1 persistent tracks'):
            construct(case(68), 4, self.capacity, self.delay)


if __name__ == '__main__':
    unittest.main()
