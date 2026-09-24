"""Three fixed synthetic inputs: static compilation and rational model only."""

import unittest

from src.q1_benchmarks.response_contract_probe import NAMES, _compare, _config, _model, fixture


class ResponseContractInputTests(unittest.TestCase):
    def test_unchanged_timing_does_not_hide_traffic_mismatch(self):
        model = dict(full=dict(makespan=4, trace=[]), quotient=dict(makespan=4),
                     compile_certificate=dict(traffic=dict(scheduled_copy_bytes=61),
                                              cross_task_tensor_bytes=0))
        official = dict(makespan=4, per_core_timeline=[], cross_task_traffic=0,
                        data_movement_bytes=dict(scheduled_copy_bytes=60))
        result = _compare(official, model)
        self.assertTrue(result['all_op_timelines_equal'])
        self.assertTrue(result['full_makespan_equal'])
        self.assertFalse(result['traffic_equal'])

    def test_three_predeclared_micrographs(self):
        capacity, bandwidth, waits = _config()
        self.assertEqual(bandwidth, 60)
        self.assertEqual(waits["task_same_core_wait_cycles"], 100)
        for name in NAMES:
            with self.subTest(name=name):
                graph, plan = fixture(name)
                self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                self.assertEqual(len(graph["ops"]), 8 if name == "symmetric-k2" else 12)
                model = _model(graph, plan, capacity, bandwidth,
                               waits["task_same_core_wait_cycles"])
                expected_rounds = 1 if name == "divergent-k3" else 2
                self.assertEqual(model["quotient"]["equal_rounds"], expected_rounds)
                self.assertEqual(model["full"]["makespan"],
                                 model["quotient"]["makespan"])
                trace = model["full"]["trace"]
                self.assertEqual(len(trace), len(plan["core_schedules"]) * 2 * 4)
                first = [op for op in trace if op["core"] == 0 and op["task"] == 0]
                mte2 = next(op for op in first if op["pipe"] == "PIPE_MTE2")
                mte3 = [op for op in first if op["pipe"] == "PIPE_MTE3"]
                self.assertTrue(any(op["start"] < mte2["end"] for op in mte3))
                self.assertTrue(any(op["work"] == 3 and op["ddr"] for op in first))
                self.assertTrue(any(op["work"] == 2 and op["ddr"] for op in first))
                self.assertEqual(model["compile_certificate"]["calls"],
                                 {"solver": 0, "E0": 0, "E1": 0, "E2": 0})


if __name__ == "__main__":
    unittest.main()
