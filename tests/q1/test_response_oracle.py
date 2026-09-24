"""Analytical miniature contracts, not official case/evaluator performance."""
import unittest
from dataclasses import replace

from src.q1.response_oracle import PortOp, Task, quotient, simulate


def dual_port_task(compute=1, incoming=2, outgoing=1, task_id=0):
    # A ready input COPY overlaps a compute operation; its output COPY starts
    # when compute completes, while the input COPY can remain in flight.
    return Task(((PortOp(compute, False, (0, 0, 0, 0), 1),), (),
                 (PortOp(incoming, True, (0, 0, 0, 0), 2),),
                 (PortOp(outgoing, True, (1, 0, 0, 0), 3),)), task_id)


class ResponseOracleTests(unittest.TestCase):
    def test_symmetric_dual_ports_two_rounds_and_gate(self):
        first = dual_port_task()
        second = replace(first, task_id=1)
        lines = [[first, second] for _ in range(3)]
        full = simulate(lines, gate=4, keep_trace=True)
        folded = quotient(lines, gate=4)
        # Per round 3*(2+1)=9 DDR cycles, continuously occupied; two
        # rounds and one four-cycle gate give 22 cycles, not 26.
        self.assertEqual(full["makespan"], 22)
        self.assertEqual(folded["makespan"], 22)
        self.assertEqual(folded["distinct_responses"], 1)
        self.assertEqual(folded["equal_rounds"], 2)
        self.assertEqual(full["service_cycles"], 18)
        input_copy = next(t for t in full["trace"]
                          if t["core"] == 0 and t["task"] == 0 and t["op_id"] == 2)
        output_copy = next(t for t in full["trace"]
                           if t["core"] == 0 and t["task"] == 0 and t["op_id"] == 3)
        self.assertLess(output_copy["start"], input_copy["end"])

    def test_fractional_service_and_first_divergence_remain_explicit(self):
        first = dual_port_task(incoming=1)
        other = dual_port_task(compute=2, incoming=1)
        full = simulate([[first], [other]], gate=0, keep_trace=True)
        folded = quotient([[first], [other]], gate=0)
        self.assertEqual(full["makespan"], 4)
        self.assertEqual(full["service_cycles"], 4)
        self.assertEqual(folded["makespan"], 4)
        self.assertEqual(folded["equal_rounds"], 0)
        self.assertEqual(folded["explicit_tail_tasks"], 2)

    def test_unequal_tail_has_no_padding_barrier(self):
        first = dual_port_task()
        tail = dual_port_task(compute=20, task_id=1)
        lines = [[first, tail], [first]]
        full = simulate(lines, gate=3)
        folded = quotient(lines, gate=3)
        self.assertEqual(folded["makespan"], full["makespan"])
        self.assertEqual(folded["equal_rounds"], 1)
        self.assertEqual(folded["explicit_tail_tasks"], 1)
        self.assertEqual(folded["tail"]["per_core_finish"][1], 0)
        # An initially empty core prevents folding instead of multiplying
        # COPY work by all available cores.
        self.assertEqual(quotient([[first], []])["equal_rounds"], 0)

    def test_invalid_prefix_is_error_not_an_optimistic_score(self):
        bad = Task(((PortOp(1, False, (1, 0, 0, 0)),), (), (), ()))
        with self.assertRaisesRegex(ValueError, "itself"):
            simulate([[bad]])
        cycle = Task(((PortOp(1, False, (0, 1, 0, 0)),),
                      (PortOp(1, False, (1, 0, 0, 0)),), (), ()))
        with self.assertRaisesRegex(ValueError, "deadlock"):
            simulate([[cycle]])


if __name__ == "__main__":
    unittest.main()
