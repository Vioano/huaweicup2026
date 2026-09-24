"""Small static witnesses only; these tests never invoke E0 or a solver."""
import unittest

from src.q3.copy_bound import UnsupportedBound, analyze


def graph(nodes, edges=(), tensors=()):
    return {"ops": [{"id": u, "op": "COMPUTE", "pipe": pipe, "cycles": cycles}
                    for u, pipe, cycles in nodes],
            "tensors": list(tensors),
            "edges": list(edges)}


def plan(*cores):
    return {"node_to_subgraph": {str(u): u for core in cores for u in core},
            "core_schedules": [list(core) for core in cores]}


def tensor_edges(u, tid, v):
    return [{"source": u, "target": tid}, {"source": tid, "target": v}]


def bound(g, p, delay=500, ddr=60, cache=250):
    return analyze(g, p, delay, ddr, cache)


class CopyBoundTests(unittest.TestCase):
    def test_explicit_copy_chain_reference(self):
        # Independent tiny DAG: u[0,4], OUT[4,6], release[6,506],
        # IN[506,507], v[507,513]. s=61 gives ceil(61/60)=2.
        g = graph([(1, "PIPE_M", 4), (2, "PIPE_V", 6)],
                  tensor_edges(1, 100, 2),
                  [{"id": 100, "pos": "UB", "size": 61}])
        result = bound(g, plan([1], [2]))
        self.assertEqual(result["legacy_bound"]["lower_bound_cycles"], 510)
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 513)
        self.assertEqual(result["copy_min_bound"]["path_ops"], [1, 2])
        self.assertEqual(result["copy_min_bound"]["charged_path_edges"][0]
                         ["charged_connections"][0]["id"], 100)
        self.assertFalse(result["execution_legality_proved"])
        self.assertEqual(result["official_evaluations"], 0)

    def test_same_pair_multiple_tensors_takes_max(self):
        g = graph([(1, "PIPE_M", 4), (2, "PIPE_V", 6)],
                  tensor_edges(1, 100, 2) + tensor_edges(1, 101, 2),
                  [{"id": 100, "pos": "L1", "size": 60},
                   {"id": 101, "pos": "UB", "size": 600}])
        result = bound(g, plan([1], [2]))
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 523)
        self.assertEqual(len(result["charged_connections"]), 2)
        self.assertEqual([x["id"] for x in result["copy_min_bound"]
                          ["charged_path_edges"][0]["charged_connections"]], [101])

    def test_graph_input_has_no_source_copy_out(self):
        g = graph([(1, "PIPE_M", 2)], [{"source": 100, "target": 1}],
                  [{"id": 100, "pos": "UB", "size": 600}])
        result = bound(g, plan([1]))
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 2)
        self.assertEqual(result["charged_connections"], [])

    def test_direct_edge_uses_data_size(self):
        g = graph([(1, "PIPE_M", 3), (2, "PIPE_V", 4)],
                  [{"source": 1, "target": 2, "data_size": 301}])
        result = bound(g, plan([1], [2]))
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 515)
        self.assertEqual(result["charged_connections"][0]["kind"], "direct")
        self.assertEqual(result["charged_connections"][0]["size_bytes"], 301)

    def test_zero_size_copies_still_take_one_cycle_each(self):
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_V", 1)],
                  [{"source": 1, "target": 2}])
        result = bound(g, plan([1], [2]))
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 504)

    def test_compute_fifo_is_preserved(self):
        g = graph([(1, "PIPE_M", 10), (2, "PIPE_M", 10),
                   (3, "PIPE_V", 1)], tensor_edges(2, 100, 3),
                  [{"id": 100, "pos": "UB", "size": 60}])
        result = bound(g, plan([1, 2], [3]))
        self.assertEqual(result["copy_min_bound"]["path_ops"], [1, 2, 3])
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 523)

    def test_slow_cache_cannot_make_necessary_bound_larger_than_ddr_path(self):
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_V", 1)],
                  [{"source": 1, "target": 2, "data_size": 600}])
        result = bound(g, plan([1], [2]), ddr=60, cache=10)
        self.assertEqual(result["copy_min_bound"]["lower_bound_cycles"], 522)

    def test_unsupported_multiple_producers_and_copy_bridge(self):
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_M", 1),
                   (3, "PIPE_V", 1)],
                  tensor_edges(1, 100, 3) + [{"source": 2, "target": 100}],
                  [{"id": 100, "pos": "UB", "size": 60}])
        with self.assertRaisesRegex(UnsupportedBound, "multiple original producers"):
            bound(g, plan([1, 2], [3]))
        bridge = graph([(1, "PIPE_M", 1), (2, "PIPE_V", 1)],
                       [{"source": 1, "target": 10},
                        {"source": 10, "target": 2}])
        bridge["ops"].append({"id": 10, "op": "COPY_OUT",
                              "pipe": "PIPE_MTE3", "cycles": 1})
        with self.assertRaisesRegex(UnsupportedBound, "COPY contraction"):
            bound(bridge, plan([1], [2]))

    def test_invalid_parameters_and_direct_size(self):
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_V", 1)],
                  [{"source": 1, "target": 2, "data_size": -1}])
        with self.assertRaisesRegex(UnsupportedBound, "data_size"):
            bound(g, plan([1], [2]))
        clean = graph([(1, "PIPE_M", 1)])
        for value in (0, -1, True, 1.5):
            with self.assertRaises(UnsupportedBound):
                bound(clean, plan([1]), ddr=value)


if __name__ == "__main__":
    unittest.main()
