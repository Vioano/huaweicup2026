"""Ledger fixtures only: no solver, E0, E1, or E2 calls."""
import unittest

from src.q1_benchmarks.s6607_structural_full500 import checked_diagnostics


def valid():
    return {"selected_plan_sha256": "final-plan-sha",
            "actual_e1_calls_total": 4, "known_e1_calls_lower_bound": 4,
            "extra_score_attempts": 1, "extra_actual_e1_calls": 1,
            "parent": {"baseline": {"actual_e1_calls": 2,
                                    "diagnostics": {"online_scores": [{"worker_pid": 11},
                                                                       {"worker_pid": 12}]}},
                       "refinement": {"score_attempts": 1, "actual_e1_calls": 1,
                                      "score": {"worker_pid": 13}}},
            "extra": [{"score_attempted": True, "score": {"worker_pid": 14}}]}


class LedgerTests(unittest.TestCase):
    def test_valid_fixture(self):
        self.assertEqual(checked_diagnostics(valid(), "final-plan-sha"), 4)

    def test_tampered_counts_and_missing_pid_rejected(self):
        for path, value in (("extra_actual_e1_calls", 0),
                            ("extra_score_attempts", 0),
                            ("actual_e1_calls_total", 3),
                            ("known_e1_calls_lower_bound", 3)):
            with self.subTest(path=path):
                diag = valid()
                diag[path] = value
                with self.assertRaises(RuntimeError):
                    checked_diagnostics(diag, "final-plan-sha")
        diag = valid()
        diag["extra"][0]["score"].pop("worker_pid")
        with self.assertRaises(RuntimeError):
            checked_diagnostics(diag, "final-plan-sha")
        diag = valid()
        diag["parent"]["refinement"]["actual_e1_calls"] = 0
        with self.assertRaises(RuntimeError):
            checked_diagnostics(diag, "final-plan-sha")

    def test_selected_plan_hash_must_match_bytes(self):
        with self.assertRaisesRegex(RuntimeError, "selected plan hash"):
            checked_diagnostics(valid(), "other-plan-sha")


if __name__ == "__main__":
    unittest.main()
