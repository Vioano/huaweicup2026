"""Committed placement words, checked with an independent enhanced DAG; no E0."""
from copy import deepcopy
import unittest

from src.q3.attention_rows import construct
from src.q3.construct import Index, derive_multicore_plan
from test_attention_gap_generalization import varied_graph
from test_attention_rows import dag_timing, plan_words


class AttentionWitnessTests(unittest.TestCase):
    def test_sixty_fixed_structures(self):
        checked = 0
        for seed in range(10):
            for panels in (1, 2):
                for ffn_count in (0, 1, 2):
                    graph = varied_graph(seed, panels, ffn_count)
                    original = deepcopy(graph)
                    index = Index(graph)
                    cores = 1 + (seed + panels + ffn_count) % 5
                    kwargs = dict(cross_delay=5, pack_ffn=bool(ffn_count),
                                  placement_mode="gap")
                    ready, ready_meta = construct(index, cores, **kwargs)
                    self.assertEqual((ready, ready_meta),
                                     construct(index, cores, final_order="ready", **kwargs))
                    plan, meta = construct(index, cores, final_order="placement", **kwargs)
                    self.assertEqual(graph, original)
                    self.assertEqual(meta["final_order"], "placement")
                    self.assertTrue(meta["strategy"].endswith("_placement_word"))
                    self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                    self.assertEqual(plan["node_to_subgraph"], ready["node_to_subgraph"])
                    words = plan_words(plan)
                    self.assertEqual(len(words), cores)
                    self.assertEqual({u for word in words for u in word}, set(index.ops))
                    self.assertEqual(sum(map(len, words)), len(index.ops))
                    derive_multicore_plan(graph, plan)

                    witness = {int(u): times for u, times in meta["placement_witness"].items()}
                    self.assertEqual(set(witness), set(index.ops))
                    owner = {u: c for c, word in enumerate(words) for u in word}
                    for u in index.ops:
                        self.assertEqual(witness[u]["finish"],
                                         witness[u]["start"] + index.duration(u))
                        for v in index.succ[u]:
                            self.assertGreaterEqual(
                                witness[v]["start"], witness[u]["finish"]
                                + (5 if owner[u] != owner[v] else 0))
                    for word in words:
                        for pipe in ("PIPE_M", "PIPE_V"):
                            lane = [u for u in word if index.ops[u]["pipe"] == pipe]
                            for u, v in zip(lane, lane[1:]):
                                self.assertGreaterEqual(witness[v]["start"],
                                                        witness[u]["finish"])
                    starts, finishes = dag_timing(index, words, 5)
                    self.assertTrue(all(starts[u] <= witness[u]["start"]
                                        and finishes[u] <= witness[u]["finish"]
                                        for u in index.ops))
                    self.assertLessEqual(max(finishes.values()),
                                         meta["proxy_makespan_cycles"])
                    self.assertEqual(meta["proxy_makespan_cycles"],
                                     meta["placement_proxy_makespan_cycles"])
                    checked += 1
        self.assertEqual(checked, 60)

    def test_unknown_final_order_rejected(self):
        graph = varied_graph(0, 1, 0)
        with self.assertRaisesRegex(ValueError, "final_order"):
            construct(Index(graph), 2, final_order="unknown")

    def test_append_placement_word_uses_same_witness_contract(self):
        graph = varied_graph(2, 2, 1)
        index = Index(graph)
        plan, meta = construct(index, 3, cross_delay=7, pack_ffn=True,
                               final_order="placement")
        words = plan_words(plan)
        _, finishes = dag_timing(index, words, 7)
        self.assertLessEqual(max(finishes.values()), meta["proxy_makespan_cycles"])
        self.assertEqual(meta["proxy_makespan_cycles"],
                         meta["placement_proxy_makespan_cycles"])
        derive_multicore_plan(graph, plan)
