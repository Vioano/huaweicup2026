"""Read-only provenance checks; never launch the solver or an evaluator."""
import unittest

from src.q1_yuanzhifang_stage_k import benchmark_k as runner


class ApprovedReuse(unittest.TestCase):
    def test_approved_feed_has_exactly_one_k4_e0_record_per_case(self):
        rows, identity = runner.load_reuse_feed(
            runner.ROOT / runner.APPROVED_REUSE_FEED, runner.APPROVED_REUSE_COMMIT)
        self.assertEqual(len(rows), 100)
        self.assertEqual({case for case, _ in rows}, {f"{i:03d}" for i in range(1, 101)})
        self.assertEqual(identity["feed_sha256"], runner.APPROVED_REUSE_SHA256)

    def test_other_source_is_rejected_before_reuse(self):
        with self.assertRaisesRegex(ValueError, "parent-approved"):
            runner.load_reuse_feed(runner.ROOT / runner.APPROVED_REUSE_FEED, "0" * 40)

    def test_fixed_budget_and_no_retry(self):
        self.assertEqual((runner.MAX_SOLVER, runner.MAX_E1_ATTEMPTS, runner.MAX_NEW_E0),
                         (100, 700, 8))
        self.assertEqual((runner.SOLVER_TIMEOUT, runner.E0_TIMEOUT, runner.BATCH_TIMEOUT),
                         (120, 180, 2400))
        self.assertEqual(runner.MIN_AVAILABLE_RAM_BYTES, 3 * (1 << 29))
        self.assertEqual(runner.JOB_MEMORY_BYTES, 1 << 30)


if __name__ == "__main__":
    unittest.main()
