"""Synthetic static guards only; never run a returned official Task prefix."""

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q3 import pipeline_prefix as prefix


def two_step_graph():
    # At op 2, tensor 11 is still an input while tensor 12 is allocated.
    return {
        "ops": [{"id": 1}, {"id": 2}],
        "tensors": [
            {"id": 11, "pos": "L1", "size": 6},
            {"id": 12, "pos": "L1", "size": 5},
        ],
        "edges": [
            {"source": 1, "target": 11},
            {"source": 11, "target": 2},
            {"source": 2, "target": 12},
        ],
    }


class IntervalPeakGuardTests(unittest.TestCase):
    def test_closed_input_output_overlap_at_same_operation(self):
        graph = two_step_graph()
        self.assertEqual(prefix._interval_peaks(graph, [1, 2], {"L1": 11, "UB": 1}),
                         {"L1": 11, "UB": 0})

    def test_capacity_one_below_closed_peak_fails(self):
        with self.assertRaisesRegex(prefix.GuardFailure,
                                    r"closed-interval peak L1 11>10"):
            prefix._interval_peaks(two_step_graph(), [1, 2],
                                   {"L1": 10, "UB": 1})

    def test_initial_on_chip_resident_rejected(self):
        graph = {"ops": [{"id": 1}],
                 "tensors": [{"id": 11, "pos": "UB", "size": 3}],
                 "edges": [{"source": 11, "target": 1}]}
        with self.assertRaisesRegex(prefix.GuardFailure,
                                    "initial on-chip resident tensor"):
            prefix._interval_peaks(graph, [1], {"L1": 1, "UB": 3})

    def test_topology_and_tensor_mediation_rejected(self):
        with self.assertRaisesRegex(prefix.GuardFailure, "word violates a data edge"):
            prefix._interval_peaks(two_step_graph(), [2, 1],
                                   {"L1": 11, "UB": 1})
        graph = two_step_graph()
        graph["edges"].append({"source": 1, "target": 2})
        with self.assertRaisesRegex(prefix.GuardFailure,
                                    "requires tensor-mediated edges only"):
            prefix._interval_peaks(graph, [1, 2], {"L1": 11, "UB": 1})


class FrozenPrefixGuardTests(unittest.TestCase):
    def test_source_path_and_hash_fail_closed_then_extract_without_calling(self):
        # A function that would fail if invoked proves extraction itself does not
        # execute the Task builder body. No generated prefix is called here.
        source = (b"def _build_scene_b_tasks(graph, plan, bandwidth, capacity):\n"
                  b"    raise AssertionError('Task builder executed')\n"
                  b"    tasks_data = {}\n"
                  b"    cross_links = []\n"
                  b"    plan_view = {}\n"
                  b"    tasks = {}\n")
        with tempfile.TemporaryDirectory() as directory:
            frozen = Path(directory) / "frozen.py"
            frozen.write_bytes(source)
            with (patch.object(prefix, "OFFICIAL_SOURCE", frozen),
                  patch.object(prefix, "OFFICIAL_SHA256", hashlib.sha256(source).hexdigest())):
                with patch.object(prefix.scene_b, "__file__", str(frozen) + ".other"):
                    with self.assertRaisesRegex(prefix.GuardFailure,
                                                "not the frozen source path"):
                        prefix._official_prefix()
                with patch.object(prefix.scene_b, "__file__", str(frozen)):
                    with patch.object(prefix, "OFFICIAL_SHA256", "0" * 64):
                        with self.assertRaisesRegex(prefix.GuardFailure,
                                                    "frozen P3 source SHA differs"):
                            prefix._official_prefix()
                    extracted = prefix._official_prefix()
                    self.assertTrue(callable(extracted))
                    self.assertEqual(extracted.__name__, "_static_scene_b_prefix")


if __name__ == "__main__":
    unittest.main()
