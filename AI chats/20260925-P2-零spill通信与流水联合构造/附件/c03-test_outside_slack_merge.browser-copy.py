"""Synthetic-only checks for C03. No official graph/evaluator imports or reads."""
from __future__ import annotations
import json
import random
import unittest
from fractions import Fraction
from pathlib import Path
from collections import Counter

from outside_slack_merge import FixedModel, NoCandidate, recover, lift_priority, emit_plan, topological


def fixed_asap(model, rows):
    """DAG recurrence for an explicitly fixed-service synthetic model."""
    edges = dict(model.lags)
    for row in rows:
        pipes = {}
        for u in row:
            pipes.setdefault(model.pipe[u], []).append(u)
        for jobs in pipes.values():
            for u, v in zip(jobs, jobs[1:]):
                edges[u, v] = max(edges.get((u, v), 0), 0)
    succ = {u: set() for u in model.duration}
    pred = {u: [] for u in model.duration}
    for (u, v), lag in edges.items():
        succ[u].add(v); pred[v].append((u, lag))
    starts = {}
    for v in topological(succ):
        starts[v] = max([model.release[v]] + [starts[u] + model.duration[u] + lag for u, lag in pred[v]])
    return starts, max(starts[u] + model.duration[u] for u in starts)


def fair_fixed_arrivals(requests):
    """Exact rational fluid service accounting for declared synthetic arrivals.

    No graph reconstruction, ready-queue scheduler or Pipe decisions.
    The two fixtures have already compatible per-MTE request starts.
    """
    arrivals = sorted((Fraction(t), name, Fraction(work)) for name, t, work in requests)
    active, finish = {}, {}
    j = 0; now = Fraction(0)
    while j < len(arrivals) or active:
        while j < len(arrivals) and arrivals[j][0] == now:
            _, name, work = arrivals[j]
            active[name] = work; j += 1
        if not active:
            now = arrivals[j][0]
            continue
        next_finish = now + min(active.values()) * len(active)
        then = min(next_finish, arrivals[j][0]) if j < len(arrivals) else next_finish
        share = (then - now) / len(active)
        active = {name: work - share for name, work in active.items()}
        now = then
        for name in list(active):
            if active[name] == 0:
                finish[name] = now; del active[name]
    return finish


REPORT = {'scope': 'Only synthetic fixed-service DAGs and exact rational COPY service fixtures',
          'official_graphs_constructed': 0, 'official_evaluator_calls': 0,
          'randomized': {}, 'fixtures': {}}


class Tests(unittest.TestCase):
    def test_allowed_exterior_lateness(self):
        # Exterior E=0(V,4) is allowed to finish at 6 rather than 4.
        model = FixedModel({0:4,1:2,2:2,3:8}, {0:'V',1:'V',2:'M',3:'M'}, {(1,2):0}, dict.fromkeys(range(4),0))
        rows = [[0,1,2],[3]]
        old = {0:0,1:4,2:6,3:0}
        result = recover(model, rows, old, [1,2], 0, 8)
        starts, end = fixed_asap(model, result['rows'])
        self.assertEqual(starts[0],2)
        self.assertEqual(end,8)
        self.assertEqual(result['exterior_reserved_start'][0],2)
        self.assertEqual(starts[2]+2,4)
        plan = emit_plan({'node_to_subgraph':{str(u):100+u for u in old}, 'core_schedules':[[100,101,102],[103]]},result)
        self.assertEqual(set(plan), {'node_to_subgraph','core_schedules'})
        REPORT['fixtures']['exterior_can_finish_later_without_makespan_loss'] = {
            'old_exterior_E_finish':4, 'new_E_finish':6, 'fixed_model_M':8,
            'old_exit_finish':8,'new_exit_finish':4}

    def test_future_ready_head(self):
        # Exterior E=0(V,10)->T=3(V,100) and P=2(M,100)->R=1(V,1).
        model = FixedModel({0:10,1:1,2:100,3:100}, {0:'V',1:'V',2:'M',3:'V'},
                           {(2,1):0,(0,3):0}, dict.fromkeys(range(4),0))
        good = [[0,1],[2,3]]
        old, baseline = fixed_asap(model,good)
        bad = [[1,0],[2,3]]
        _, delayed = fixed_asap(model,bad)
        self.assertEqual((baseline,delayed),(110,211))
        result = recover(model,good,old,[1],0,baseline)
        self.assertEqual(result['rows'],good)
        REPORT['fixtures']['topological_ready_is_not_time_ready'] = {'outside_first':110,'region_first':211}

    def test_fragmented_midpoint_is_not_complete(self):
        model = FixedModel({0:2,1:3,2:1,3:6}, {0:'V',1:'V',2:'M',3:'M'}, {(1,2):0}, dict.fromkeys(range(4),0))
        old_rows = [[0,2],[1],[3]]
        old = {0:0,1:0,2:3,3:0}
        with self.assertRaises(NoCandidate) as cm:
            recover(model,old_rows,old,[1,2],0,6)
        self.assertEqual(cm.exception.code,'no_fit_for_frozen_midpoint_and_word')
        # Legal different exterior slack allocation, deliberately NOT searched by kernel.
        _, feasible_M = fixed_asap(model,[[1,0,2],[],[3]])
        self.assertEqual(feasible_M,6)
        REPORT['fixtures']['midpoint_false_negative'] = {
            'reserved_V_interval':[2,4], 'needed_contiguous_V_service':3,
            'constructor':'no_candidate', 'another_legal_fixed_model_M':6}

    def test_temporal_witness_may_not_lift(self):
        model = FixedModel(dict.fromkeys(range(4),1), {0:'M',1:'V',2:'V',3:'M'}, {(2,3):0}, dict.fromkeys(range(4),0))
        old_rows = [[0,1,3],[2]]
        witness = {1:0,2:1,3:2,0:3}
        with self.assertRaises(NoCandidate) as cm:
            lift_priority(model,old_rows,[2,3],dict.fromkeys(range(4),0),witness)
        self.assertEqual(cm.exception.code,'priority_lift_cycle')
        REPORT['fixtures']['priority_lift_cycle'] = {'valid_resource_witness':witness,'cycle':[0,1,2,3,0]}

    def test_ddr_can_invalidate_model_certificate(self):
        # E=0(M,20), r=1(M,1), z=2(M,1), a=3(V,1000).
        # Baseline: core0=[a,z], core1=[E,r]. r->z carries 60 B;
        # a's boundary COPY_IN carries 600 B; z's output carries 3000 B.
        # Pure compute candidate model omits COPY and uses the new local r->z lag 0.
        model = FixedModel({0:20,1:1,2:1,3:1000}, {0:'M',1:'M',2:'M',3:'V'}, {(1,2):0}, dict.fromkeys(range(4),0))
        rows = [[3,2],[0,1]]
        old_start = {0:0,1:20,2:523,3:10}
        result = recover(model,rows,old_start,[1,2],0,1010)
        self.assertTrue(result['fixed_service_witness_valid'])
        self.assertFalse(result['official_nonregression_certified'])
        old_ddr = fair_fixed_arrivals([('A_in',0,10),('r_out',21,1),('r_in',522,1),('z_out',524,50)])
        new_ddr = fair_fixed_arrivals([('A_in',0,10),('z_out',2,50)])
        self.assertEqual(old_ddr, {'A_in':10,'r_out':22,'r_in':523,'z_out':574})
        self.assertEqual(new_ddr, {'A_in':18,'z_out':60})
        old_M=max(old_ddr['A_in']+1000,old_ddr['z_out'])
        new_M=max(new_ddr['A_in']+1000,new_ddr['z_out'])
        self.assertEqual((old_M,new_M),(1010,1018))
        REPORT['fixtures']['shared_DDR_counterexample'] = {
            'old_exit_finish':524,'new_exit_finish':2,'old_fixed_release_fluid_M':int(old_M),
            'new_fixed_release_fluid_M':int(new_M), 'old_DDR_service':62,'new_DDR_service':60,
            'old_A_copy_finish':10,'new_A_copy_finish':18,
            'constructor_rows':result['rows'],
            'scope':'Source-semantics-derived synthetic schedule; not an official evaluator run'}

    def test_1000_random_fixed_models(self):
        rng = random.Random(70328)
        counts=Counter()
        for _ in range(1000):
            n=rng.randint(4,18); k=rng.randint(2,3)
            nodes=list(range(n)); owners={u:rng.randrange(k) for u in nodes}
            rows=[[u for u in nodes if owners[u]==c] for c in range(k)]
            pipe={u:rng.choice(['M','V']) for u in nodes}
            durations={u:rng.randint(1,9) for u in nodes}
            arcs={(u,v) for u in nodes for v in range(u+1,n) if rng.random()<0.13}
            lag0={(u,v):2*int(owners[u]!=owners[v]) for u,v in arcs}
            baseline=FixedModel(durations,pipe,lag0,dict.fromkeys(nodes,0))
            old, horizon=fixed_asap(baseline,rows)
            region=sorted(rng.sample(nodes,rng.randint(1,min(6,n-1))))
            host=rng.randrange(k); newowners={u:host if u in region else owners[u] for u in nodes}
            lag1={(u,v):2*int(newowners[u]!=newowners[v]) for u,v in arcs}
            model=FixedModel(durations,pipe,lag1,dict.fromkeys(nodes,0))
            try:
                result=recover(model,rows,old,region,host,horizon)
            except NoCandidate as exc:
                counts[exc.code]+=1
                continue
            counts['success']+=1
            actual,M=fixed_asap(model,result['rows'])
            self.assertLessEqual(M,horizon)
            for u in nodes:
                self.assertLessEqual(actual[u],result['witness_start'][u])
            for c,row in enumerate(rows):
                self.assertEqual([u for u in row if u not in region],
                                 [u for u in result['rows'][c] if u not in region])
        self.assertGreater(counts['success'],0)
        REPORT['randomized']={'generated_fixed_service_cases':1000,'seed':70328,'outcomes':dict(counts),
                              'successes_checked_by_independent_longest_path_recurrence':counts['success'],
                              'not_performance_evidence':True}


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    REPORT['tests_run']=result.testsRun
    REPORT['tests_successful']=result.wasSuccessful()
    Path(__file__).with_name('synthetic_results.json').write_text(json.dumps(REPORT,indent=2,ensure_ascii=False)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
