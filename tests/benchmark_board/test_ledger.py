import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/benchmark_board'))
from core import Ledger, packed, digest
class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.man={'official_code_hash':'a'*64,'files':[{'path':'data/config.txt','sha256':'b'*64},{'path':'data/case_002.json','sha256':'c'*64}]}
        self.l=Ledger(Path(self.temp.name),self.man);self.blobs={};self.source={'commit':'d'*40,'path':'results/feed.json'}
    def artifact(self,name,obj):
        data=packed(obj).encode();path='results/'+name;self.blobs[path]=data;return {'path':path,'sha256':digest(data)}
    def record(self,attempt='test-a',makespan=100):
        plan=self.artifact(attempt+'plan.json',{'node_to_subgraph':{},'core_schedules':{}})
        result=self.artifact(attempt+'result.json',{'scene':'B','problem':3,'cache_mode':'read_only','num_cores':4,'makespan':makespan})
        run=self.artifact(attempt+'run.json',{'test_fixture':True})
        return {'attempt_id':attempt,'revision':1,'run_id':'synthetic-test-only','algorithm_id':'fixture','algorithm_name':'fixture','solver_commit':'1'*40,'problem':'P3','case_id':'002','cores':4,'status':'ok','metrics':{'makespan_cycles':makespan},'evaluator':{'route':'E0','commit':'2'*40,'entrypoint':'test'},'identity':{'official_sha256':'a'*64,'config_sha256':'b'*64,'graph_sha256':'c'*64,'plan_sha256':plan['sha256']},'artifacts':{'plan':plan,'result':result,'run':run}}
    def put(self,*rows): return self.l.ingest({'schema_version':1,'records':list(rows)},lambda p:self.blobs[p],self.source)
    def best(self):return next(c for c in self.l.snapshot()['cells'] if c['problem']=='P3' and c['case_id']=='002' and c['cores']==4)['best']
    def test_best_history_idempotence_and_restart(self):
        a=self.record();b=self.record('test-b',80);self.put(a,b);self.assertEqual(self.best()['metrics']['makespan_cycles'],80);self.assertEqual(self.put(a,b)['added'],0);self.assertEqual(len(self.l.records()),2)
        again=Ledger(Path(self.temp.name),self.man);self.assertEqual(len(again.events(0)),2)
    def test_withdraw_keeps_history_and_reverts(self):
        a=self.record();b=self.record('test-b',80);self.put(a,b);b.update(revision=2,status='withdrawn');self.put(b);self.assertEqual(self.best()['metrics']['makespan_cycles'],100);self.assertEqual(len(self.l.records()),3)
    def test_conflict_atomic(self):
        a=self.record();self.put(a);b=self.record('test-b');a['notes']=['different'];
        with self.assertRaises(ValueError):self.put(b,a)
        self.assertEqual(len(self.l.records()),1)
    def test_source_e2_e1_unapproved_wrong_identity_not_ranked(self):
        for mode in ('E2','E1','wrong'):
            r=self.record(mode)
            if mode=='wrong':r['identity']['config_sha256']='f'*64
            else:r['evaluator']['route']=mode
            self.put(r)
        self.assertIsNone(self.best());self.assertEqual(len(self.l.records()),3)
    def test_artifact_mismatch_and_float_type(self):
        r=self.record();r['metrics']['makespan_cycles']=100.0;self.put(r);self.assertIsNone(self.best())
        r=self.record('bad');self.blobs[r['artifacts']['plan']['path']]=b'bad';self.put(r);self.assertIsNone(self.best())
    def test_cache_pair_needs_same_plan(self):
        r=self.record();pair=dict(r['identity'],route='E0',cores=4,result=self.artifact('pair.json',{'scene':'B','num_cores':4,'makespan':150}));r['cache_pair']=pair
        self.put(r);self.assertEqual(self.best()['metrics']['cache_gain'],1.5)
        r.update(revision=2);r['cache_pair']['plan_sha256']='f'*64;self.put(r);self.assertIsNone(self.best()['metrics'].get('cache_gain'))
    def test_baseline_no_stub(self):
        r=self.record();r['baseline']=dict(r['identity'],route='E0',entrypoint='stub',result=self.artifact('baseline.json',{'scene':'A','num_cores':1,'makespan':250}));self.put(r);self.assertFalse(self.best()['baseline_verified'])
        r.update(revision=2);r['baseline']['entrypoint']='singlecore_evaluate.evaluate_singlecore';self.put(r);self.assertEqual(self.best()['metrics']['baseline_speedup'],2.5)
    def test_missing_zero_and_bad_numbers(self):
        for x in (0,-1,float('nan'),True):
            r=self.record(makespan=1);r['metrics']['makespan_cycles']=x
            with self.assertRaises(ValueError):self.put(r)
    def test_failure_never_uses_last_metric(self):
        r=self.record();r['status']='timeout';self.put(r);self.assertIsNone(self.best());self.assertIsNone(self.l.records()[0]['metrics']['makespan_cycles'])
    def test_preview_never_displaces_verified(self):
        a=self.record();b=self.record('report',1);b['artifacts']={};self.put(a,b)
        c=next(c for c in self.l.snapshot(include_reported=True)['cells'] if c['problem']=='P3' and c['case_id']=='002' and c['cores']==4)
        self.assertEqual(c['best']['metrics']['makespan_cycles'],100)
    def test_reported_numerator_with_verified_baseline_is_not_admitted(self):
        r=self.record();r['artifacts']={}
        r['baseline']=dict(r['identity'],route='E0',entrypoint='singlecore_evaluate.evaluate_singlecore',result=self.artifact('single.json',{'scene':'A','num_cores':1,'makespan':250}))
        self.put(r);row=self.l.records()[0]
        self.assertEqual(row['metrics']['baseline_speedup'],2.5)
        self.assertTrue(row['baseline_verified']);self.assertFalse(row['eligible']);self.assertIsNone(self.best())
        r['revision']=2;r['identity']['config_sha256']='f'*64;self.put(r)
        self.assertIsNone(self.l.records()[-1]['metrics'].get('baseline_speedup'))
    def test_official_p3_identity_and_no_cache_pair_are_distinct(self):
        r=self.record('native-p3');self.put(r);self.assertTrue(self.best()['eligible'])
        for name,result in [('old-c',{'scene':'C'}),('plain-b',{'scene':'B'}),('missing-mode',{'scene':'B','problem':3})]:
            row=self.record(name);row['artifacts']['result']=self.artifact(name+'.json',dict(result,num_cores=4,makespan=100));self.put(row)
            self.assertFalse(self.l.records()[-1]['eligible'])
        r['revision']=2
        r['cache_pair']=dict(r['identity'],route='E0',cores=4,result=self.artifact('bad-no-cache.json',{'scene':'B','problem':3,'cache_mode':'read_only','num_cores':4,'makespan':150}))
        self.put(r);self.assertFalse(self.l.records()[-1]['cache_pair_verified'])
        r['revision']=3;r['identity']['config_sha256']='b'*64;r['evaluator']['route']='E2';self.put(r)
        self.assertIsNone(self.l.records()[-1]['metrics'].get('baseline_speedup'))
if __name__=='__main__':unittest.main()
