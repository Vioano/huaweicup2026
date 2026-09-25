"""Pure output and call-budget guards; no official Task compiler imported."""
import tempfile
import unittest
from pathlib import Path

from src.review.p1_memory_cache_probe import CompileBudget, create_output


class ProbeGuards(unittest.TestCase):
    def test_budget_reserves_before_call(self):
        budget = CompileBudget(1)
        budget.reserve()
        self.assertEqual((budget.attempts_reserved, budget.confirmed_completed), (1, 0))
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            budget.reserve()

    def test_requires_execute_and_new_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "new"
            with self.assertRaisesRegex(ValueError, "--execute"):
                create_output(path, execute=False)
            self.assertFalse(path.exists())
            create_output(path, execute=True)
            with self.assertRaises(FileExistsError):
                create_output(path, execute=True)


if __name__ == "__main__":
    unittest.main()
