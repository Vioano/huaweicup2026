import unittest

from src.q1.shared_input_full_core import construct, UnsupportedStructure
from tests.q1.test_component_pack import graph


def fixture(size):
    g = graph([(u, "V", 10) for u in (1, 2, 3)], [])
    g["tensors"].append({"id": 900, "size": size, "pos": "UB"})
    g["edges"].extend({"source": 900, "target": u} for u in (1, 2, 3))
    return g


class FullCoreTests(unittest.TestCase):
    def test_forces_all_requested_cores(self):
        plan, info = construct(fixture(600000), 3)
        self.assertEqual(info["active_cores"], 3)
        self.assertTrue(all(plan["core_schedules"]))
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})

    def test_domain_guard(self):
        with self.assertRaises(UnsupportedStructure):
            construct(fixture(524288), 3)


if __name__ == "__main__":
    unittest.main()
