"""One pure-process recovery: five toy tests then old R9 prepared readback."""
import gzip,hashlib,json,unittest
from pathlib import Path
from src.q3.layered_prepared_guard import check_layered_prepared
ROOT=Path(__file__).resolve().parents[5]
FILES={
 'graph':('data/raw/a/official/data/case_005.json','c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f'),
 'plan':('results/a/q3-nikolastarx/layered-one-shot-20260925/candidate/case_005_multicore_res.json','2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
 'prepared':('results/a/q3-nikolastarx/layered-one-shot-20260925/run/prepared.json.gz','91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44')}
def read(k):
 p,h=FILES[k];p=ROOT/p;raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=h:raise ValueError(k+' hash differs')
 return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_q3_multibucket_guard')
 outcome=unittest.TextTestRunner(verbosity=2).run(suite)
 if not outcome.wasSuccessful() or outcome.testsRun!=5:raise SystemExit('toy suite failed; archived readback not started')
 graph,plan,prepared=(read(k) for k in ('graph','plan','prepared'))
 old=check_layered_prepared(graph,plan,prepared,layers=3)
 multi=check_layered_prepared(graph,plan,prepared,layers=3,allow_multi=True,crossing_limit=None)
 assert old['status']==multi['status']=='passed'
 result={'schema':'q3-multibucket-guard-recovery-v1','toy_tests':outcome.testsRun,
   'old_status':old['status'],'multi_status':multi['status'],
   'old_crossing':old['max_crossing'],'multi_crossing':multi['max_crossing'],
   'multi_crossing_bound_certified':multi['crossing_bound_certified'],
   'multi_complete_seq_closed_interval_peaks':multi['complete_seq_closed_interval_peaks'],
   'inputs_sha256':{k:v[1] for k,v in FILES.items()},'official_calls':0}
 (Path(__file__).parent/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'toy_tests':outcome.testsRun,'old':old['status'],'multi':multi['status']}))
