"""Pure acyclic DP tests; no graph, official Task compilation or scoring."""

import unittest

from src.q1.memory_packet_probe import solve_acyclic


class MemoryPacketDPTests(unittest.TestCase):
    def test_drain_closure_at_same_layer(self):
        costs = {(0, 0, 1, 1, False): (1, 0, 1),
                 (1, 1, 0, 0, True): (1, 0, 1),
                 (1, 0, 1, 0, False): (1, 0, 1),
                 (0, 0, 2, 0, False): (10, 0, 1)}
        result = solve_acyclic(
            2, 1, 2, lambda *args: costs.get(args),
            lambda r, policy: (0, 0, 0) if r == 0 and policy == 'merge' else None)
        self.assertEqual(result['cost'], (3, 0, 3))
        self.assertEqual(result['actions'],
                         ((0, 0, 1, 1), (1, 1, 0, 0), (1, 0, 1, 0)))

    def test_same_cost_table_compares_old_q1_and_new_q2(self):
        def transition(n, r, q, s, drain):
            if r or s or drain:
                return None
            return {(1, 1): (4, 0, 1), (0, 2): (5, 0, 1),
                    (0, 1): (4, 0, 1)}.get((n, q))
        terminal = lambda r, policy: (0, 0, 0) if r == 0 and policy == 'merge' else None
        old = solve_acyclic(2, 0, 1, transition, terminal)
        new = solve_acyclic(2, 2, 2, transition, terminal)
        self.assertEqual(old['cost'][0], 8)
        self.assertEqual(new['cost'][0], 5)
        self.assertEqual(new['actions'], ((0, 0, 2, 0),))


if __name__ == '__main__':
    unittest.main()
