"""Synthetic structural and fake compiler/model checks; no official Task calls."""
import unittest
from types import SimpleNamespace
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from src.review import p1_real_work_phase_probe as probe


def fixture(count=10, cores=2):
    chains = [[3*i+j for j in range(3)] for i in range(count*cores)]
    ops = [{'id':u,'op':'ADD','pipe':'PIPE_M' if j in (0,2) else 'PIPE_V',
            'cycles': (3,4,3)[j]}
           for chain in chains for j,u in enumerate(chain)]
    class Family:
        def __init__(self, *_):
            self.chains=chains
            self.bins=[chains[k::cores] for k in range(cores)]
            self.view=SimpleNamespace(ops={x['id']:x for x in ops})
            self.family_certificate={'kind':'fake-private'}
    return {'ops':ops}, Family


class PhaseProbeTests(unittest.TestCase):
    def test_cli_failure_keeps_validated_plans_and_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph=Path(tmp)/'input.json';graph.write_text('{}')
            out=Path(tmp)/'out';digest=hashlib.sha256(graph.read_bytes()).hexdigest()
            plan={'node_to_subgraph':{'1':0},'core_schedules':[[0],[]]}
            report={'status':'unknown','plans_validated':True,
                    'compile_certificate':{'traffic':{'scheduled_copy_bytes':2}},
                    'error':'fake Fraction timeout'}
            argv=['probe',str(graph),'--cores','2','--capacity-l1','1','--capacity-ub','1',
                  '--bandwidth','60','--gate','100','--q','1','--s','1','--period','10',
                  '--chain-work','10','--threshold','99264','--expect-graph-sha256',digest,
                  '--output-root',str(out),'--execute']
            with patch('sys.argv',argv),patch.object(probe,'run',return_value=(plan,plan,report)),self.assertRaises(SystemExit) as raised:
                probe.main()
            self.assertEqual(raised.exception.code,2)
            self.assertEqual(json.loads((out/'control-plan.json').read_text()),plan)
            self.assertEqual(json.loads((out/'phase-plan.json').read_text()),plan)
            self.assertEqual(json.loads((out/'diagnostics.json').read_text())['compile_certificate'],report['compile_certificate'])

    def params(self):
        return (2, {'L1':524288,'UB':131072}, 60, 100, 1, 1, 10, 10, 99264)

    def test_same_partition_compiled_once_and_reordered_twice(self):
        graph, family=fixture()
        compiled=[];seen=[]
        class Task:
            def __init__(self, task_id):self.task_id=task_id
            def signature(self):return ('synthetic',self.task_id)
            ports=((SimpleNamespace(work=1,ddr=False,need=(0,0,0,0),original_id=1),),(),(),())
        def compiler(g, plan, capacity, bandwidth):
            compiled.append(plan)
            lines=[[Task(t) for t in order] for order in plan['core_schedules']]
            return lines, {'traffic':{'scheduled_copy_bytes':123},'compiler_source_hashes':{}}
        def score(lines, gate, limit):
            seen.append([[t.task_id for t in line] for line in lines])
            return {'makespan':100 if len(seen)==1 else 90,'events':5,'trace':[{'core':0,'task':1}]}, .01
        control, phase, report=probe.run(graph,*self.params(),family_factory=family,
            validate=lambda *_:None,compiler=compiler,scorer=score)
        self.assertEqual(report['status'],'model_pair_complete_NOT_E0')
        self.assertEqual(len(compiled),1)
        self.assertEqual(seen,[control['core_schedules'],phase['core_schedules']])
        self.assertEqual(control['node_to_subgraph'],phase['node_to_subgraph'])
        self.assertTrue(report['suggest_independent_E0'])
        self.assertEqual(report['calls']['Task_compile_confirmed'],report['task_count'])
        self.assertEqual(report['calls']['Fraction_attempts'],2)
        self.assertEqual(report['control_model']['trace'],[{'core':0,'task':1}])
        self.assertEqual(report['compile_certificate']['traffic']['scheduled_copy_bytes'],123)
        self.assertEqual(len(report['compiled_ports']),report['task_count'])

    def test_false_chain_work_stops_before_compilation(self):
        graph,family=fixture();calls=[]
        _,_,report=probe.run(graph,2,{'L1':524288,'UB':131072},60,100,1,1,10,11,99264,
            family_factory=family,compiler=lambda *args:calls.append(1))
        self.assertEqual(calls,[])
        self.assertIn('chain work',report['error'])

    def test_over_task_budget_stops_before_compile(self):
        graph,family=fixture()
        calls=[]
        def too_many(*args,**kwargs):
            plan={'node_to_subgraph':{},'core_schedules':[list(range(13)),list(range(13,26))]}
            return plan,plan,{}
        _,_,report=probe.run(graph,*self.params(),family_factory=family,
            build_pair=too_many,validate=lambda *_:None,
            compiler=lambda *args:calls.append(1),scorer=lambda *args:calls.append(2))
        self.assertEqual(calls,[])
        self.assertEqual(report['status'],'unknown')
        self.assertEqual(report['calls']['Task_compile_attempted_upper_bound'],0)

    def test_model_failure_preserves_one_attempt_and_no_recommendation(self):
        graph,family=fixture();calls=[]
        class Task:
            def __init__(self, task_id):self.task_id=task_id
            def signature(self):return (self.task_id,)
            ports=((SimpleNamespace(work=1,ddr=False,need=(0,0,0,0),original_id=1),),(),(),())
        def compiler(g,plan,*_):
            return [[Task(t) for t in line] for line in plan['core_schedules']], {'traffic':{'scheduled_copy_bytes':1},'compiler_source_hashes':{}}
        def score(*args):
            calls.append(1)
            raise TimeoutError('fake 30s')
        _,_,report=probe.run(graph,*self.params(),family_factory=family,
            validate=lambda *_:None,compiler=compiler,scorer=score)
        self.assertEqual(calls,[1])
        self.assertEqual(report['calls']['Fraction_attempts'],1)
        self.assertNotIn('suggest_independent_E0',report)
        self.assertEqual(report['failed_stage'],'control_Fraction')
        self.assertTrue(report['plans_validated'])
        self.assertEqual(len(report['compiled_ports']),report['task_count'])

if __name__=='__main__':unittest.main()
