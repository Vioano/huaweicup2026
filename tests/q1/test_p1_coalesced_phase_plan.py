"""Pure Task partition/order tests; no official compile, model or E0."""
import unittest
from src.review.p1_coalesced_phase_plan import construct_pair, UnsupportedPhase


def bins(counts, length=4):
    cursor=1;lines=[]
    for count in counts:
        line=[]
        for _ in range(count):
            chain=list(range(cursor,cursor+length));cursor+=length;line.append(chain)
        lines.append(line)
    return lines


def call(lines, **changes):
    args=dict(q=7,s=3,body_period=35405,chain_compute_work=4512,
              compute_ids_in_input_order=[u for line in lines for c in line for u in c])
    args.update(changes)
    return construct_pair(lines,**args)


class CoalescedPlanTests(unittest.TestCase):
    def test_unequal_five_core_counts_same_partition_reordered(self):
        lines=bins([22,22,22,21,21]);control,phase,info=call(lines)
        self.assertEqual(info['whole_chain_reserve'],7)
        self.assertEqual(info['phase_counts'],[0,2,3,5,6])
        self.assertEqual(info['tasks'],27)
        self.assertEqual(info['tasks_per_core'],[5,6,6,5,5])
        self.assertEqual(control['node_to_subgraph'],phase['node_to_subgraph'])
        self.assertEqual(set(control),{'node_to_subgraph','core_schedules'})
        mapping=control['node_to_subgraph']
        self.assertEqual(len(mapping),sum(map(len,[c for line in lines for c in line])))
        for a,b in zip(control['core_schedules'],phase['core_schedules']):
            self.assertEqual(set(a),set(b))
            self.assertEqual(len(a),len(set(a)))
        self.assertNotEqual(control['core_schedules'],phase['core_schedules'])
        self.assertEqual(info['body_packets'],2)

    def test_no_empty_reserve_task_when_first_shift_zero(self):
        control,phase,info=call(bins([21]*5))
        self.assertEqual(info['phase_counts'][0],0)
        self.assertEqual(control['core_schedules'][0][0],phase['core_schedules'][0][-1])
        self.assertEqual(info['tasks_per_core'][0],4)

    def test_no_empty_after_segment_when_shift_equals_reserve(self):
        lines=bins([10,10]);ids=[u for line in lines for c in line for u in c]
        control,phase,info=construct_pair(lines,q=1,s=1,body_period=10,
            chain_compute_work=10,compute_ids_in_input_order=ids)
        self.assertEqual((info['whole_chain_reserve'],info['phase_counts']),(1,[0,1]))
        self.assertEqual(info['tasks_per_core'],[11,11])
        self.assertEqual(control['core_schedules'][1],phase['core_schedules'][1])

    def test_duplicate_and_incomplete_id_family_rejected(self):
        lines=bins([21]*5);lines[1][0][0]=lines[0][0][0]
        with self.assertRaises(ValueError):call(lines)
        lines=bins([21]*5)
        with self.assertRaises(ValueError):call(lines,compute_ids_in_input_order=[1])

    def test_reject_insufficient_or_imbalanced_family(self):
        with self.assertRaises(UnsupportedPhase):call(bins([10]*5))
        with self.assertRaises(UnsupportedPhase):call(bins([22,20,22,21,21]))
        with self.assertRaises(UnsupportedPhase):call(bins([21]*5),max_tasks_per_core_budget=3)

if __name__=='__main__':unittest.main()
