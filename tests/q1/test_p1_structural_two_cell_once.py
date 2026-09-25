"""Fake-only contract tests; never run solver, E1 or official E0."""
import importlib.util,json,pathlib,tempfile
import os,gzip
SRC=pathlib.Path(__file__).resolve().parents[2]/'src/review/p1_structural_two_cell_once.py'
spec=importlib.util.spec_from_file_location('two_cell',SRC);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture(root,fail_solver=False,bad_diag=False):
 m.ROOT=root;m.OFFICIAL=root/'data/raw/a/official';(m.OFFICIAL/'code').mkdir(parents=True);(m.OFFICIAL/'data').mkdir()
 m.proc_table=lambda:{os.getpid():(1,1000,1024)};m.repo_owned=lambda birth,table:{}
 for c in m.CASES:
  f=root/f'case_{c}.json';f.write_text('{"ops":[]}');m.GRAPH_SHA[c]=m.sha(f)
 def fake(argv,folder,name,timeout,input_root):
  assert timeout==(180 if name=='solver' else 120)
  (folder/f'{name}.stdout.txt').write_text('fake stdout');(folder/f'{name}.stderr.txt').write_text('fake stderr')
  if name=='solver':
   if fail_solver:return {'status':'failed','cleanup_confirmed':True}
   plan=pathlib.Path(argv[argv.index('--output')+1]);plan.write_text(json.dumps({'node_to_subgraph':{},'core_schedules':[[],[],[],[],[]]}))
   diag=pathlib.Path(argv[argv.index('--diagnostics')+1]);
   if not bad_diag:diag.write_text(json.dumps({'actual_e1_calls_total':8,'selected_plan_sha256':m.sha(plan),'parent':{'baseline':{'diagnostics':{'actual_e1_calls':6,'online_scores':[]}},'refinement':{'actual_e1_calls':0}},'extra':[]}))
   return {'status':'ok','cleanup_confirmed':True}
  result=pathlib.Path(argv[argv.index('--output')+1]);result.write_text(json.dumps({'scene':'A','num_cores':5,'makespan':12,'data_movement_bytes':{}}))
  pathlib.Path(argv[argv.index('--trace-output')+1]).write_text('{}');pathlib.Path(argv[argv.index('--log-output')+1]).write_text('official fake')
  return {'status':'ok','cleanup_confirmed':True}
 return fake
def test_two_cells_dispatch_once_and_keep_exact_calls():
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);fake=fixture(root);out=root/'result';m.main(out,fake,lambda:0);r=json.loads((out/'attempt.json').read_text())
  assert r['status']=='complete' and r['calls']=={'solver':2,'E1':16,'E0':2,'E2':0,'retry':0},r
  for c in m.CASES:
   d=out/c;assert all((d/n).is_file() for n in (f'case_{c}_multicore_res.json','diagnostics.json','result.json','trace.json','official.log','solver.stdout.txt','solver.stderr.txt','E0.stdout.txt','E0.stderr.txt'))
def test_first_failure_stops_and_unknown_ledger_never_scores():
 for options in ({'fail_solver':True},{'bad_diag':True}):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);fake=fixture(root,**options);out=root/'result'
   try:m.main(out,fake,lambda:0)
   except SystemExit as exc:assert exc.code==1
   else:raise AssertionError('failed run must stop')
   r=json.loads((out/'attempt.json').read_text());assert r['status']=='stopped' and r['calls']['E0']==0
   assert r['cells'][0]['status']=='failed' and r['cells'][1]['status']=='not_run'
def test_saved_051_diagnostic_shape_is_accepted_without_scoring():
 p=pathlib.Path(__file__).resolve().parents[2]/'results/a/p1-structural-runner-pilot-20260925/public/cells/051/k5/diagnostics.json.gz'
 d=json.loads(gzip.decompress(p.read_bytes()));assert m.diag_ok(d) and d['actual_e1_calls_total']==4
def test_host_fake_ack_before_new_and_stop_readback():
 import time
 pre=pathlib.Path(__file__).resolve().parents[2]/'results/a/p1-structural-two-cell-20260925/preflight';spec=importlib.util.spec_from_file_location('host_ctrl',pre/'controller.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c);c.HERE=pre
 pin=m.sha(pre/'artifact-manifest.json');events=[]
 class WD:
  def cancel(self):events.append('watchdog-cancel')
 def runner(label,argv,timeout):
  events.append(label)
  if label in ('preflight-sessions','finally-sessions'):return {'returncode':0,'stdout':'No active sessions found on server.','stderr':''}
  if label=='download':pathlib.Path(argv[-1]).write_bytes(b'fake raw package');return {'returncode':0,'stdout':'','stderr':''}
  return {'returncode':0,'stdout':'','stderr':''}
 with tempfile.TemporaryDirectory() as td:
  result=c.run_once(runner=runner,watchdog_start=lambda s,d:(events.append('watchdog-ack') or WD()),verify=lambda _: {'status':'complete','calls':{'solver':2,'E0':2}},now=time.monotonic,persist=lambda _:None,cli='/fake/colab',artifact_manifest_sha256=pin,archive=pathlib.Path(td)/'archive.tar.gz')
 assert result['status']=='e0-success-collected' and result['VM_stopped_readback']
 assert events.index('watchdog-ack')<events.index('new') and 'finally-stop' in events and 'finally-sessions' in events

def test_expired_before_dispatch_keeps_failed_and_unrun_cells():
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);fake=fixture(root);out=root/'result'
  try:m.main(out,fake,lambda:0,deadline_monotonic=1)
  except SystemExit as exc:assert exc.code==1
  else:raise AssertionError('expired run must fail before dispatch')
  r=json.loads((out/'attempt.json').read_text())
  assert r['calls']=={'solver':0,'E1':0,'E0':0,'E2':0,'retry':0}
  assert [x['status'] for x in r['cells']]==['failed','not_run']

def test_verifier_rejects_plan_substitution_even_with_rehashed_archive():
 import hashlib,io,tarfile
 pre=SRC.parents[2]/'results/a/p1-structural-two-cell-20260925/preflight'
 spec=importlib.util.spec_from_file_location('evidence_verify',pre/'controller_draft.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 enc=lambda x:(json.dumps(x)+'\n').encode();sha=lambda b:hashlib.sha256(b).hexdigest()
 cells=[];data={};calls={'solver':2,'E1':16,'E0':2,'E2':0,'retry':0}
 process={'status':'ok','exit_code':0,'cleanup_confirmed':True,'adopted_cleanup':{'confirmed':True},'process_identity':{'pid':42,'pgid':42,'linux_proc_start_ticks':100}}
 for case,digest in v.GRAPH.items():
  base=f'workspace/two-cell-run/{case}/';plan=enc({'node_to_subgraph':{},'core_schedules':[[],[],[],[],[]]})
  data[base+f'case_{case}_multicore_res.json']=plan
  data[base+'diagnostics.json']=enc({'actual_e1_calls_total':8,'selected_plan_sha256':sha(plan)})
  data[base+'result.json']=enc({'scene':'A','num_cores':5,'makespan':12})
  for leaf in ('trace.json','official.log','solver.stdout.txt','solver.stderr.txt','solver.stdout.raw.txt','solver.stderr.raw.txt','E0.stdout.txt','E0.stderr.txt','E0.stdout.raw.txt','E0.stderr.raw.txt'):data[base+leaf]=b'fake'
  cells.append({'case':case,'status':'ok','graph_sha256':digest,'plan_sha256':sha(plan),'makespan_cycles':12,'calls':{'solver':1,'E1':8,'E0':1},'solver':process,'evaluation':process})
 data['workspace/two-cell-run/attempt.json']=enc({'status':'complete','worker_cleanup':{'confirmed':True},'calls':calls,'cells':cells})
 data['evidence/setup.json']=enc({'status':'complete','runner_exit':0,'runner_exited':True,'adopted_cleanup':{'confirmed':True},'stage_child_cleanup':{'confirmed':True}})
 def pack(path):
  files=dict(data);files['evidence/evidence-manifest.json']=enc({'files':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in sorted(data.items())]})
  with tarfile.open(path,'w:gz') as t:
   for p,b in files.items():i=tarfile.TarInfo(p);i.size=len(b);t.addfile(i,io.BytesIO(b))
 with tempfile.TemporaryDirectory() as td:
  path=pathlib.Path(td)/'evidence.tar.gz';pack(path);assert v.verify_evidence(path)['status']=='complete'
  data['workspace/two-cell-run/016/case_016_multicore_res.json']+=b' '
  pack(path)
  try:v.verify_evidence(path)
  except ValueError as exc:assert 'identity mismatch' in str(exc)
  else:raise AssertionError('rehashed substituted plan accepted')
