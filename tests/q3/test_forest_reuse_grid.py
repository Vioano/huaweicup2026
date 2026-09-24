import copy
import unittest

from src.q3.construct import Index, UnsupportedStructure
from src.q3.forest_reuse_grid import construct, recognize, balanced_slices


def grid_graph(rows=3, columns=4):
    graph = {"ops": [], "tensors": [], "edges": []}
    oid, tid = 1, 10000

    def op(kind, pipe, cycles=1):
        nonlocal oid
        u = oid
        oid += 1
        graph["ops"].append({"id": u, "op": kind, "pipe": pipe, "cycles": cycles})
        return u

    def tensor(size, pos="L1"):
        nonlocal tid
        t = tid
        tid += 1
        graph["tensors"].append({"id": t, "size": size, "pos": pos})
        return t

    def edge(a, b):
        graph["edges"].append({"source": a, "target": b})

    def input_tensor(size):
        raw, local = tensor(size, "DDR"), tensor(size)
        c = op("COPY_IN", "PIPE_MTE2")
        edge(raw, c)
        edge(c, local)
        return local

    a = [input_tensor(1000) for _ in range(rows)]
    b = [input_tensor(10) for _ in range(columns)]
    for i in range(rows):
        for j in range(columns):
            leaves = []
            for _ in range(2):
                u, t = op("MATMUL", "PIPE_M", 10), tensor(3)
                edge(a[i], u)
                edge(b[j], u)
                edge(u, t)
                leaves.append(t)
            join, result = op("ADD", "PIPE_V"), tensor(3)
            for t in leaves:
                edge(t, join)
            edge(join, result)
            out, raw = op("COPY_OUT", "PIPE_MTE3"), tensor(3, "DDR")
            edge(result, out)
            edge(out, raw)
    return graph


class ReuseGridTests(unittest.TestCase):
    def test_axes_come_from_actual_reader_sets(self):
        index = Index(grid_graph())
        model = recognize(index)
        self.assertEqual(sorted(map(len, model["axes"])), [3, 4])
        self.assertEqual(len(model["cells"]), 12)
        for (a, b), component in model["cells"].items():
            self.assertEqual(set(model["memberships"][component]), {a, b})

    def test_balanced_whole_trees_reduce_copy_floor(self):
        index = Index(grid_graph())
        plan, meta = construct(index, 3)
        self.assertLess(sum(meta["input_copy_floor_bytes_by_core"]),
                        sum(meta["old_input_copy_floor_bytes_by_core"]))
        self.assertEqual(list(map(len, meta["components_by_core"])), [4, 4, 4])
        schedule_core = {sg: c for c, word in enumerate(plan["core_schedules"]) for sg in word}
        for component in index.components:
            self.assertEqual(len({schedule_core[plan["node_to_subgraph"][str(u)]] for u in component}), 1)
        self.assertEqual(set(plan["node_to_subgraph"]), set(map(str, index.ops)))

    def test_incomplete_grid_rejected_even_with_two_input_groups_per_cell(self):
        graph = grid_graph()
        index = Index(graph)
        remove = set(index.components[-1])
        graph["ops"] = [o for o in graph["ops"] if o["id"] not in remove]
        graph["edges"] = [e for e in graph["edges"] if e["source"] not in remove and e["target"] not in remove]
        with self.assertRaises(UnsupportedStructure):
            recognize(Index(graph))

    def test_heterogeneous_compute_rejected_and_cells_not_dropped(self):
        graph = copy.deepcopy(grid_graph())
        next(o for o in graph["ops"] if o["op"] == "MATMUL")["cycles"] += 1
        with self.assertRaisesRegex(UnsupportedStructure, "identical"):
            recognize(Index(graph))
        self.assertEqual(balanced_slices(list(range(13)), 5),
                         [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10], [11, 12]])


if __name__ == "__main__":
    unittest.main()
