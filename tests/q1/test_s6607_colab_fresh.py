"""Fixture-only dispatcher tests; never start a solver or evaluator."""
import tempfile
from pathlib import Path
import unittest

from src.q1_benchmarks import s6607_colab_fresh as target


class ColabFreshTests(unittest.TestCase):
    def test_explicit_matrix_selection(self):
        self.assertEqual(len(target.parse_cells(None, None, True)), 500)
        self.assertEqual(target.parse_cells("001,002", "2,5", False),
                         [("001", 2), ("001", 5), ("002", 2), ("002", 5)])
        with self.assertRaises(ValueError):
            target.parse_cells("001", "1", True)

    def test_first_failure_stops_and_preserves_unknown_ledger(self):
        calls = []
        def fake(cell, *_):
            calls.append(cell)
            return dict(case_id=cell[0], cores=cell[1], status="failed",
                        calls=dict(solver=1, E1=None, E0=0, E2=0),
                        failure={"stage": "synthetic"})
        with tempfile.TemporaryDirectory(dir=target.ROOT) as temp:
            out = Path(temp) / "fresh-batch"
            status = target.run(out, [("001", 1), ("002", 2)],
                                process_cell=fake, verify=False)
            self.assertEqual(status, 1)
            self.assertEqual(calls, [("001", 1)])
            meta = target.h.read(out / "batch.json")
            self.assertIsNone(meta["actual_calls"]["E1"])
            self.assertEqual(meta["known_calls_lower_bound"]["solver"], 1)
            self.assertEqual(target.h.read(out / "cells/002/k2/run.json")["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
