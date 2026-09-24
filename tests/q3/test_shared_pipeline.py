"""Small structural/DP checks only; no solver or evaluator runs."""
import ast
import copy
from itertools import combinations, product
import subprocess
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan
from src.q3.shared_pipeline import _original_tensor_views
from src.q3.shared_pipeline import construct, partition


def graph(jobs=4, cycles=(2, 3, 4)):
    out = {"ops": [{"id": 900, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0}],
           "tensors": [{"id": 1000, "pos": "DDR", "size": 32},
                       {"id": 1001, "pos": "L1", "size": 32}],
           "edges": [{"source": 1000, "target": 900},
                     {"source": 900, "target": 1001}]}
    for j in range(jobs):
        ids = [10 * j + i for i in range(len(cycles))]
        for i, u in enumerate(ids):
            out["ops"].append({"id": u, "op": "RELU", "pipe": "PIPE_V",
                               "cycles": cycles[i]})
        out["edges"].append({"source": 1001, "target": ids[0]})
        out["edges"].extend({"source": u, "target": v}
                            for u, v in zip(ids, ids[1:]))
    return out


class SharedPipelineTests(unittest.TestCase):
    def test_dp_against_exhaustive_positive_weights(self):
        for n in range(1, 6):
            for weights in product((1, 2, 4), repeat=n):
                for stages in range(1, n + 1):
                    cuts, value = partition(weights, stages)
                    truth = min(max(sum(weights[a:b]) for a, b in zip(boundaries, boundaries[1:]))
                                for interior in combinations(range(1, n), stages - 1)
                                for boundaries in ([0, *interior, n],))
                    self.assertEqual(value, truth)
                    self.assertEqual((cuts[0], cuts[-1], len(cuts)), (0, n, stages + 1))
        # Fang 6bae uses the smallest preceding cut on equal objective values.
        self.assertEqual(partition([2, 2, 2], 2), ([0, 1, 3], 4))

    def test_plan_parity_and_derive(self):
        source = graph()
        before = copy.deepcopy(source)
        index = Index(source)
        plan, meta = construct(index, 2)
        # Fixed small fixture parity with 6bae pipeline_stages: weights=(2,3,4),
        # cuts=(0,2,3); each stage visits all jobs in component order.
        self.assertEqual(meta["cuts"], [0, 2, 3])
        self.assertEqual(meta["stage_compute_cycles"], [5, 4])
        expected = [[index.components[j][p] for j in range(4) for p in (0, 1)],
                    [index.components[j][2] for j in range(4)]]
        inverse = {v: int(u) for u, v in plan["node_to_subgraph"].items()}
        self.assertEqual([[inverse[s] for s in word] for word in plan["core_schedules"]], expected)
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(index.ops))
        self.assertEqual(len(set(s for word in plan["core_schedules"] for s in word)), len(index.ops))
        derive_multicore_plan(source, plan)
        self.assertEqual(meta["shared_input_bytes_by_stage"], [32, 0])
        self.assertEqual(source, before)
        self.assertEqual((plan, meta), construct(index, 2))

    def test_fixed_upstream_function_parity(self):
        """Execute only the published functions against the same small Index."""
        revision = "6bae8dfa317bc71226068344b59dd65d2612c32b"
        def original(name, functions):
            result = subprocess.run(
                ["git", "show", f"{revision}:src/q3_yuanzhifang/{name}.py"],
                check=True, capture_output=True, text=True,
            )
            module = ast.parse(result.stdout)
            selected = ast.Module(body=[node for node in module.body
                                        if isinstance(node, ast.FunctionDef)
                                        and node.name in functions], type_ignores=[])
            scope = {"_original_tensor_views": _original_tensor_views,
                     "derive_multicore_plan": derive_multicore_plan}
            exec(compile(selected, f"{name}@{revision}", "exec"), scope)
            return scope
        upstream_guard = original("active_stages", {"stage_structure"})
        upstream = original("pipeline_stages", {"partition", "build"})
        upstream["stage_structure"] = upstream_guard["stage_structure"]
        upstream["active_build"] = lambda *_: self.fail("upstream fallback unexpectedly called")
        source = graph()
        index = Index(source)
        # The original SharingIndex adds these data views to the same base Index.
        producers, consumers, _ = _original_tensor_views(source)
        owner = {u: j for j, job in enumerate(index.components) for u in job}
        index.inputs = [set() for _ in index.components]
        for tensor, readers in consumers.items():
            if not any(u in index.ops for u in producers[tensor]):
                for u in readers:
                    if u in owner:
                        index.inputs[owner[u]].add(tensor)
        index.sizes = {t["id"]: t["size"] for t in source["tensors"]}
        self.assertEqual(construct(index, 2), upstream["build"](index, 2, 1))

    def test_guards(self):
        with self.assertRaises(UnsupportedStructure):
            construct(Index(graph(jobs=1)), 2)
        with self.assertRaises(ValueError):
            construct(Index(graph()), True)
        changed = graph()
        changed["ops"][4]["cycles"] += 1
        with self.assertRaises(UnsupportedStructure):
            construct(Index(changed), 2)
        branched = graph()
        branched["edges"] = [edge for edge in branched["edges"]
                             if edge != {"source": 0, "target": 1}]
        branched["edges"].append({"source": 0, "target": 2})
        with self.assertRaises(UnsupportedStructure):
            construct(Index(branched), 2)
        absent = graph()
        absent["edges"] = [edge for edge in absent["edges"]
                            if edge != {"source": 1001, "target": 10}]
        with self.assertRaises(UnsupportedStructure):
            construct(Index(absent), 2)


if __name__ == "__main__":
    unittest.main()
