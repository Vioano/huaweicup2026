"""Independent small-window oracle and read-only original graph checks."""
import copy
import json
from pathlib import Path
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan
from src.q3.forest_memory_order import construct as forest_order
from src.q3.stagger_tile import _envelope, _ports, _word, transform
from src.q3.leaf_tile import _chains
from src.q3.forest_reuse_grid import recognize
from tests.q3.test_leaf_tile import grid_graph


ROOT = Path(__file__).resolve().parents[2]


def brute_envelope(word, ins, outs, external, sizes):
    first, last = {}, {}
    for j, u in enumerate(word):
        for tid in (*ins[u], outs[u]):
            first.setdefault(tid, j)
            last[tid] = j
    values = []
    for j in range(len(word)):
        live = {t for t in first if t not in external and first[t] <= j <= last[t]}
        begun = {t for t in first if first[t] <= j <= last[t]}
        horizon = max((last[t] for t in begun), default=j)
        incoming = {t for h in range(j, horizon + 1) for t in ins[word[h]] if t in external}
        values.append(sum(sizes[t] for t in live | incoming))
    return max(values, default=0)


def owners(plan):
    by_sg = {sg: core for core, seq in enumerate(plan["core_schedules"]) for sg in seq}
    return {int(u): by_sg[sg] for u, sg in plan["node_to_subgraph"].items()}


class StaggerTileTests(unittest.TestCase):
    def test_small_lifetimes_against_direct_windows(self):
        graph, _, _ = grid_graph(m=2, n=2, leaves=3, a=13, b=7, s=3)
        index = Index(graph)
        words, *_ = _chains(index, recognize(index))
        ins, outs, external, sizes = _ports(index, words)
        cells = [(0, 0, 0), (0, 1, 1), (1, 0, 2), (1, 1, 3)]
        for width in (1, 2, 4):
            for offset in range(0, 4, width):
                word = _word(words, cells[offset:offset + width], 3)
                self.assertEqual(_envelope(word, ins, outs, external, sizes)[0],
                                 brute_envelope(word, ins, outs, external, sizes))

    def test_shape_guard_and_owner_preservation(self):
        graph, _, _ = grid_graph(m=2, n=3, leaves=3, a=13, b=7, s=3)
        index = Index(graph)
        base, _ = forest_order(index, 2)
        plan, meta = transform(index, base, 200)
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(plan["node_to_subgraph"], base["node_to_subgraph"])
        self.assertEqual(owners(plan), owners(base))
        self.assertLessEqual(max(meta["protected_bound_bytes_by_core"]), 200)
        self.assertGreater(meta["feasible_shapes"], 0)
        derive_multicore_plan(graph, plan)

    def test_single_cell_tile_degenerates_without_loss(self):
        graph, _, _ = grid_graph(m=2, n=2, leaves=2, a=13, b=7, s=3)
        index = Index(graph)
        base, _ = forest_order(index, 1)
        words, *_ = _chains(index, recognize(index))
        ins, outs, external, sizes = _ports(index, words)
        lower = max(_envelope(_word(words, [(0, 0, cid)], 2), ins, outs, external, sizes)[0]
                    for cid in words)
        # A conservative buffer condition can make the exact minimum larger.
        plan, meta = transform(index, base, max(lower, 7 * 3 + 13 + 7 + 13 + 7))
        self.assertEqual(meta["tile_shape"], [1, 1])
        self.assertEqual(owners(plan), owners(base))

    def test_misplaced_leaf_ordinal_is_rejected(self):
        graph, matmuls, col = grid_graph(m=2, n=2)
        bad = copy.deepcopy(graph)
        u0, u1 = matmuls[0, 0, 0], matmuls[0, 0, 1]
        for edge in bad["edges"]:
            if edge["target"] == u0 and edge["source"] == col[0][0]:
                edge["source"] = col[0][1]
            elif edge["target"] == u1 and edge["source"] == col[0][1]:
                edge["source"] = col[0][0]
        index = Index(bad)
        base, _ = forest_order(index, 1)
        with self.assertRaises(UnsupportedStructure):
            transform(index, base, 1000)

    def test_cross_cell_signature_does_not_hide_within_chain_cycle_variation(self):
        original, _, _ = grid_graph(m=2, n=2, leaves=3)
        for kind, ordinal, new_cycles in (("MATMUL", 1, 11), ("ADD", 1, 3)):
            with self.subTest(kind=kind):
                graph = copy.deepcopy(original)
                index = Index(graph)
                words, *_ = _chains(index, recognize(index))
                changed = {pair[0 if kind == "MATMUL" else 1][ordinal]
                           for pair in words.values()}
                for op in graph["ops"]:
                    if op["id"] in changed:
                        op["cycles"] = new_cycles
                index = Index(graph)
                base, _ = forest_order(index, 1)
                with self.assertRaisesRegex(UnsupportedStructure, "uniform positive"):
                    transform(index, base, 1000)

    def test_original_097_static_plan(self):
        graph = json.loads((ROOT / "data/raw/a/official/data/case_097.json").read_text())
        index = Index(graph)
        base, _ = forest_order(index, 1)
        plan, meta = transform(index, base, 524288)
        self.assertEqual(meta["tile_shape"], [8, 4])
        self.assertEqual(max(meta["protected_bound_bytes_by_core"]), 518144)
        self.assertEqual(owners(plan), owners(base))
        self.assertEqual(plan["node_to_subgraph"], base["node_to_subgraph"])
        self.assertEqual(len(plan["core_schedules"][0]), len(index.ops))
        derive_multicore_plan(graph, plan)


if __name__ == "__main__":
    unittest.main()
