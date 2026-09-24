"""Small structural/R checks only; these do not call E0 or its Task compiler."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from prefetch_frontier import construct
from test_star_frontier import model_graph, WAITS
from star_frontier import guarded_stages


class PrefetchTests(unittest.TestCase):
    def test_complete_chains_and_independent_joint_rank(self):
        for shape in ("balanced", "comb"):
            for rounds in (1, 2, 24):
                graph = model_graph(rounds, shape)
                plan, info = construct(graph, 5, WAITS)
                mapping = plan["node_to_subgraph"]
                self.assertEqual(set(mapping), {o["id"] for o in graph["ops"]})
                self.assertEqual(info["task_count"], 6 * rounds)
                # Independent arithmetic for this structure: first round has
                # two three-chain cores; later only root core has four chains.
                self.assertEqual(info["model_r_cycles"], 7431 + (rounds - 1) * 8727)
                arcs = {(mapping[e["source"]], mapping[e["target"]]) for e in graph["edges"]
                        if mapping[e["source"]] != mapping[e["target"]]}
                arcs.update((a, b) for seq in plan["core_schedules"] for a, b in zip(seq, seq[1:]))
                self.assertTrue(all(a < b for a, b in arcs))
                guarded, _ = guarded_stages(graph)
                for entry in guarded["rounds"]:
                    for chain in entry["chains"]:
                        self.assertEqual(len({mapping[u] for u in chain}), 1)

    def test_fallback_and_non_numeric_names(self):
        graph = model_graph(2, "balanced")
        remap = {o["id"]: 9000 - 7 * o["id"] for o in graph["ops"]}
        for o in graph["ops"]:
            o["id"] = remap[o["id"]]
        for e in graph["edges"]:
            e["source"], e["target"] = remap[e["source"]], remap[e["target"]]
        graph["edges"].reverse()
        self.assertEqual(construct(graph, 5, WAITS)[1]["model_r_cycles"], 16158)
        graph["ops"][2]["pipe"] = "PIPE_M"
        self.assertEqual(construct(graph, 5, WAITS)[1]["selected"], "fork-fallback")
        self.assertEqual(construct(model_graph(1, "comb"), 4, WAITS)[1]["selected"], "fork-fallback")
        for cores in (True, 0, 6, 5.0):
            with self.assertRaises(ValueError):
                construct(graph, cores, WAITS)


if __name__ == "__main__":
    unittest.main()
