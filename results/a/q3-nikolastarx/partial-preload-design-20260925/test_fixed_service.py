"""Check the closed form against direct fixed-service chain execution, not E0."""
import unittest
from fixed_service import select_prefix


def direct(reads, uses, release, gate, compute, q):
    read_end, clock = [], 0
    for w in reads[:q]:
        clock += w
        read_end.append(clock)
    start = max(clock, release) + gate
    clock = start
    for w in reads[q:]:
        clock += w
        read_end.append(clock)
    clock, spent = start, 0
    for at, ready in zip(uses, read_end):
        clock = max(clock + at - spent, ready)
        spent = at
    return clock + compute - spent


class FixedServiceTests(unittest.TestCase):
    def test_closed_form(self):
        fixtures = [([1,8],[0,2],1,1,3), ([1,8],[0,2],10,1,3),
                    ([3,2,7],[0,0,5],4,2,9), ([3,2,7],[0,3,8],0,2,10),
                    ([1],[0],0,1,1), ([],[],3,2,5)]
        for reads,uses,r,d,c in fixtures:
            feasible = list(range(len(reads)+1))
            chosen, times = select_prefix(reads,uses,r,d,c,reversed(feasible))
            expected = {q:direct(reads,uses,r,d,c,q) for q in feasible}
            self.assertEqual(times,expected)
            self.assertEqual(chosen,min(feasible,key=lambda q:(expected[q],-q)))

    def test_structurally_restricted_candidates(self):
        q,times=select_prefix([1,8],[0,2],1,1,3,[2,0,2])
        self.assertNotIn(1,times)
        self.assertEqual(q,min(times,key=lambda x:(times[x],-x)))

    def test_wrong_read_order_rejected(self):
        with self.assertRaises(ValueError):
            select_prefix([1,8],[2,0],1,1,3,[1,2])

    def test_bad_prefix_rejected(self):
        for bad in ([3], [True], []):
            with self.assertRaises(ValueError):
                select_prefix([1,8],[0,2],1,1,3,bad)


if __name__=='__main__':
    unittest.main()
