"""Synthetic structural checks only; imports no official code and opens no cases."""
from __future__ import annotations
import json
import random
import unittest
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from port_packet_stationary import (
    IR, Tensor, NoCandidate, build, views, packetize, quotient, topological,
    exact_bytes, evaluate_ports, emit_singletons, PIPES, POOLS,
)

OBSERVATIONS = {}


def synthetic_bucket_lifetimes(ir, rows):
    """Pure incidence/sequence check for canonical COPY anchoring, NOT execution.

    Within each original-op bucket all incoming copies precede the compute and
    outgoing copies follow it. The packet envelope must dominate even this full
    local tensor-use expansion. No durations, bandwidth simulation or spill code.
    """
    ts, inputs, outputs, *_ = views(ir)
    owner = {u: c for c, row in enumerate(rows) for u in row}
    ranks = [{u: j for j, u in enumerate(row)} for row in rows]
    before, after = defaultdict(list), defaultdict(list)
    for t in ir.tensors:
        targets = {owner[v] for v in t.consumers}
        if t.producer is None:
            for c in targets:
                first = min((v for v in t.consumers if owner[v] == c), key=ranks[c].get)
                before[c, first].append(t.id)
        else:
            c = owner[t.producer]
            for dest in targets - {c}:
                first = min((v for v in t.consumers if owner[v] == dest), key=ranks[dest].get)
                before[dest, first].append(t.id)
                after[c, t.producer].append(t.id)
            if t.required_output or not t.consumers:
                after[c, t.producer].append(t.id)
    peaks = []
    for c, row in enumerate(rows):
        uses = []
        for u in row:
            uses.extend([{t} for t in sorted(before[c, u])])
            uses.append(inputs[u] | outputs[u])
            uses.extend([{t} for t in sorted(after[c, u])])
        first, last = {}, {}
        for i, tids in enumerate(uses):
            for t in tids:
                first.setdefault(t, i)
                last[t] = i
        events = defaultdict(Counter)
        for t in first:
            events[first[t]][ts[t].pool] += ts[t].size
            events[last[t]+1][ts[t].pool] -= ts[t].size
        live, peak = Counter(), dict.fromkeys(POOLS, 0)
        for i in range(len(uses)):
            live.update(events[i])
            for p in POOLS:
                peak[p] = max(peak[p], live[p])
        peaks.append(peak)
    return peaks


def verify_rows(ir, rows, detail):
    ts, _, _, _, succ, _ = views(ir)
    flat = [u for row in rows for u in row]
    assert len(flat) == len(set(flat)) == len(ir.pipe)
    g = {u: set(v) for u, v in succ.items()}
    for row in rows:
        for u, v in zip(row, row[1:]):
            g[u].add(v)
    topological(g)
    raw = synthetic_bucket_lifetimes(ir, rows)
    for c in range(len(rows)):
        for p in POOLS:
            assert raw[c][p] <= detail['prefix_envelope_peaks_bytes'][c][p]
    assert detail['arithmetic_pair_checks'] <= detail['pair_check_bound']
    mapping = {str(u): j for j, u in enumerate(sorted(ir.pipe))}
    plan = emit_singletons(mapping, rows)
    assert set(plan) == {'node_to_subgraph', 'core_schedules'}


def connected_heterogeneous():
    pipe = {0: 'PIPE_M', 100: 'PIPE_V', 101: 'PIPE_M'}
    durations = {0: 2, 100: 4, 101: 3}
    ts = [Tensor(1000, 60, 'UB', None, frozenset({0})),
          Tensor(1001, 12, 'UB', 0, frozenset(10 + 2*i for i in range(12)))]
    for group in range(3):
        ts.append(Tensor(1100+group, 600+60*group, 'L1', None,
                         frozenset(10+2*i for i in range(12) if i % 3 == group)))
    sinks = []
    for i in range(12):
        a, b = 10+2*i, 11+2*i
        pipe[a], pipe[b] = 'PIPE_M', 'PIPE_V'
        durations[a], durations[b] = 10+i % 3, 5+i % 2
        ts.append(Tensor(1200+2*i, 12+i, 'UB', a, frozenset({b})))
        ts.append(Tensor(1201+2*i, 8+i, 'UB', b, frozenset({100})))
        sinks.append(b)
    ts += [Tensor(1300, 12, 'UB', 100, frozenset({101})),
           Tensor(1301, 4, 'UB', 101, frozenset(), True)]
    return IR(pipe, durations, tuple(ts))


def random_ir(rng, n):
    pipe = {u: rng.choice(PIPES) for u in range(n)}
    duration = {u: rng.randrange(1, 20) for u in range(n)}
    tensors = []
    for j in range(3):
        users = frozenset(u for u in range(n) if rng.random() < .3)
        tensors.append(Tensor(1000+j, rng.randrange(1, 100), rng.choice(POOLS), None, users))
    for u in range(n):
        cs = frozenset(v for v in range(u+1, n) if rng.random() < .13)
        tensors.append(Tensor(2000+u, rng.randrange(1, 80), rng.choice(POOLS), u, cs))
    return IR(pipe, duration, tuple(tensors))


def check_fair_service(intervals):
    """Check fixed, hand-written tiny schedules by exact rational service integrals.

    Not an event scheduler: no operation gets a newly chosen start/end time here.
    """
    points = sorted({x for _, s, f, _ in intervals for x in (s, f)})
    service = Counter()
    for a, b in zip(points, points[1:]):
        active = [name for name, s, f, _ in intervals if s <= a and b <= f]
        if active:
            share = Fraction(b-a, len(active))
            for name in active:
                service[name] += share
    for name, _, _, q in intervals:
        assert service[name] == q, (name, service[name], q)
    return {name: str(service[name]) for name, *_ in intervals}


class CoreTests(unittest.TestCase):
    def test_nonisomorphic_one_component(self):
        ir = connected_heterogeneous()
        rows, detail = build(ir, 3, {'L1': 10000, 'UB': 10000}, width=3)
        verify_rows(ir, rows, detail)
        # Every operation is connected through the shared PRODUCED root and join,
        # not just through source-less shared inputs; durations/footprints differ.
        _, _, _, pred, succ, _ = views(ir)
        reached, stack = {0}, [0]
        while stack:
            u = stack.pop()
            for v in pred[u] | succ[u]:
                if v not in reached:
                    reached.add(v); stack.append(v)
        self.assertEqual(reached, set(ir.pipe))
        self.assertGreater(detail['packet_count'], 3)
        OBSERVATIONS['heterogeneous_connected_fixture'] = {
            'operations': len(ir.pipe), 'packet_count': detail['packet_count'],
            'core_operation_counts': [len(row) for row in rows],
            'boundary_replica_counts': detail['boundary_replica_counts'],
            'pre_step2_copy_bytes': detail['pre_step2_copy_bytes'],
            'note': 'a structural witness, NOT a score or performance result'}

    def test_random_coverage_accounting_envelopes(self):
        rng = random.Random(404)
        accepted, abstained = 0, Counter()
        for _ in range(400):
            ir = random_ir(rng, rng.randrange(5, 28))
            try:
                rows, detail = build(ir, rng.choice((2, 3)),
                                     {'L1': 100000, 'UB': 100000}, width=4)
            except NoCandidate as exc:
                abstained[str(exc)] += 1
                continue
            verify_rows(ir, rows, detail)
            accepted += 1
        self.assertGreater(accepted, 0)
        OBSERVATIONS['random_structural_checks'] = {
            'fixtures': 400, 'returned_witnesses': accepted,
            'family_abstentions': dict(abstained),
            'checked': ['coverage', 'DAG + full core-priority acyclicity',
                        'exact tensor/core byte accounting',
                        'COPY-bucket sequential lifetimes below prefix envelope',
                        'arithmetic pair budget'],
            'not_checked': ['official makespan', 'official prepared memory edges']}

    def test_two_column_port_response(self):
        from port_packet_stationary import Packet, resource_coefficients, profile_preview
        rng = random.Random(4041)
        checked = 0
        for _ in range(200):
            ir = random_ir(rng, 9)
            ts, inputs, outputs, pred, succ, order = views(ir)
            word = tuple(u for u in order if u != 0)
            packet = Packet(0, word,
                            frozenset(t for u in word for t in inputs[u] | outputs[u]),
                            dict(Counter(t for u in word for t in inputs[u])),
                            frozenset(t for u in word for t in outputs[u]),
                            word, {p:sum(ir.duration[u] for u in word if ir.pipe[u] == p)
                                   for p in PIPES})
            zero = [dict.fromkeys(PIPES, 0) for _ in range(2)]
            owner, finish = {0:1}, {0:321}
            base, _ = evaluate_ports(ir, packet, 0, zero, owner, finish, ts, inputs,
                                     bandwidth=60, delay=500)
            h, last = resource_coefficients(ir, packet, pred)
            for _ in range(8):
                availability = {p:rng.randrange(0, 2000) for p in PIPES}
                predicted, pclock = profile_preview(ir, packet, base, h, last, availability)
                direct, dclock = evaluate_ports(ir, packet, 0, [availability,zero[1]],
                                                owner, finish, ts, inputs,
                                                bandwidth=60, delay=500)
                self.assertEqual((predicted,pclock), (direct,dclock))
                checked += 1
        OBSERVATIONS['two_resource_column_identity_checks'] = checked

    def test_tight_capacity_family_abstention(self):
        rng = random.Random(4042)
        accepted, reasons = 0, Counter()
        for _ in range(150):
            ir = random_ir(rng, rng.randrange(8, 22))
            try:
                rows, detail = build(ir, 2, {'L1':250,'UB':250}, width=4)
            except NoCandidate as exc:
                reasons[str(exc)] += 1
                continue
            verify_rows(ir, rows, detail)
            accepted += 1
        OBSERVATIONS['tight_capacity_checks'] = {
            'fixtures':150, 'returned_witnesses':accepted,
            'family_abstentions':dict(reasons),
            'note':'abstention is not a P2 infeasibility claim'}

    def test_hyperedge_not_edge_count(self):
        ir = IR({0:'PIPE_M', 1:'PIPE_V', 2:'PIPE_V', 3:'PIPE_M'},
                {u:1 for u in range(4)},
                (Tensor(10, 100, 'L1', None, frozenset({0,3})),
                 Tensor(11, 12, 'UB', 0, frozenset({1,2,3}))))
        categories, total = exact_bytes(ir, {0:0, 1:1, 2:1, 3:0})
        self.assertEqual(categories['external'], 100)
        self.assertEqual(categories['cross_out_plus_in'], 24)  # not 48
        self.assertEqual(total, 124)

    def test_port_does_not_wait_for_unrelated_input(self):
        ir = IR({0:'PIPE_M', 1:'PIPE_V', 2:'PIPE_V'}, {0:1, 1:1, 2:1},
                (Tensor(10, 60, 'UB', None, frozenset({0})),
                 Tensor(11, 60000, 'L1', None, frozenset({1})),
                 Tensor(12, 1, 'UB', 0, frozenset({2})),
                 Tensor(13, 1, 'UB', 1, frozenset(), True)))
        from port_packet_stationary import Packet
        p = Packet(0, (0,1), frozenset({10,11,12,13}), {10:1,11:1},
                   frozenset({12,13}), (0,1), {'PIPE_M':1, 'PIPE_V':1})
        ts, inputs, *_ = views(ir)
        ends, _ = evaluate_ports(ir, p, 0, [dict.fromkeys(PIPES,0)], {}, {}, ts, inputs,
                                 bandwidth=60, delay=500)
        self.assertEqual(ends, {0:2,1:1001})
        OBSERVATIONS['separate_ports'] = {'early_output':2, 'unrelated_late_output':1001}

    def test_input_station_quotient_may_cycle(self):
        ir = IR({0:'PIPE_M',1:'PIPE_V',2:'PIPE_M'}, {0:1,1:1,2:1},
                (Tensor(10,60,'L1',None,frozenset({0,2})),
                 Tensor(11,60,'L1',None,frozenset({1})),
                 Tensor(12,1,'UB',0,frozenset({1})),
                 Tensor(13,1,'UB',1,frozenset({2}))))
        ps, v = packetize(ir, {'L1':1000,'UB':1000}, width=1)
        qp, qs = quotient(ps, v[4])
        self.assertEqual(topological(qs), [0,1,2])
        # Coloring first/last by shared input does not make a valid DAG quotient.
        with self.assertRaises(ValueError):
            topological({0:{1},1:{0}})

    def test_four_op_latency_counterexample(self):
        # A(M)->B(V), C(V)->D(M), one 6000B input shared by A and C.
        ir = IR({0:'PIPE_M',1:'PIPE_V',2:'PIPE_V',3:'PIPE_M'}, {u:1 for u in range(4)},
                (Tensor(10,6000,'UB',None,frozenset({0,2})),
                 Tensor(11,1,'UB',0,frozenset({1})),
                 Tensor(12,1,'UB',2,frozenset({3})),
                 Tensor(13,1,'UB',1,frozenset(),True),
                 Tensor(14,1,'UB',3,frozenset(),True)))
        stationary = {0:0,2:0,1:1,3:1}
        replicated = {0:0,1:0,2:1,3:1}
        stationary_ddr = [
            ('S0',0,100,100), ('Aout',101,102,1), ('Cout',102,103,1),
            ('Bin',602,603,1), ('Din',603,604,1),
            ('Bout',604,605,1), ('Dout',605,606,1)]
        replicated_ddr = [
            ('S0',0,200,100), ('S1',0,200,100),
            ('Bout',202,204,1), ('Dout',202,204,1)]
        check_fair_service(stationary_ddr)
        check_fair_service(replicated_ddr)
        # Valid core/pipe schedules written by hand; both cores have M=V=1.
        old_compute = {0:(100,101),2:(100,101),1:(603,604),3:(604,605)}
        new_compute = {0:(200,201),2:(200,201),1:(201,202),3:(201,202)}
        for owner, times in ((stationary,old_compute),(replicated,new_compute)):
            resources = defaultdict(list)
            for u,(s,f) in times.items():
                self.assertEqual(f-s, ir.duration[u])
                resources[owner[u],ir.pipe[u]].append((s,f))
            for intervals in resources.values():
                intervals.sort()
                self.assertTrue(all(a[1] <= b[0] for a,b in zip(intervals,intervals[1:])))
        _, low = exact_bytes(ir, stationary)
        _, high = exact_bytes(ir, replicated)
        self.assertEqual((low, high), (6006,12002))
        self.assertEqual((max(f for _,_,f,_ in stationary_ddr),
                          max(f for _,_,f,_ in replicated_ddr)), (606,204))
        OBSERVATIONS['four_compute_counterexample'] = {
            'stationary': {'copy_bytes':low, 'ideal_fair_model_M':606,
                           'per_core_M_V_work':[[1,1],[1,1]], 'input_replicas':1},
            'replicated': {'copy_bytes':high, 'ideal_fair_model_M':204,
                           'per_core_M_V_work':[[1,1],[1,1]], 'input_replicas':2},
            'validation': 'handwritten timelines checked with rational service integrals',
            'official_evaluator_calls':0}

    def test_oversize_guard(self):
        ir = IR({0:'PIPE_M'}, {0:1}, (Tensor(10,101,'UB',None,frozenset({0})),))
        with self.assertRaises(NoCandidate):
            build(ir, 2, {'L1':100, 'UB':100})


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CoreTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    payload = {'scope':'synthetic mathematical/structural checks ONLY',
               'tests_run':result.testsRun, 'failures':len(result.failures),
               'errors':len(result.errors), 'passed':result.wasSuccessful(),
               'official_graphs_constructed':0, 'official_evaluator_calls':0,
               'observations':OBSERVATIONS}
    Path(__file__).with_name('synthetic_results.json').write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
