"""Pure gate/route replay, no graph construction or evaluator call."""
import copy,hashlib,importlib.util,json,subprocess,sys,tempfile,time,shutil
from datetime import datetime,timedelta,timezone
from pathlib import Path
H=Path(__file__).absolute().parent;R=H.parents[1]
spec=importlib.util.spec_from_file_location('q',H/'run.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
m=q.read(H/'manifest.json')
with tempfile.TemporaryDirectory() as t:
 t=Path(t);g=t/'gate.json';out=Path(m['output_dir']);pins={'status':'admitted','scope':q.SCOPE,'manifest_sha256':q.sha(H/'manifest.json'),'runner_sha256':q.sha(H/'run.py'),'holdout_runner_sha256':m['holdout_runner_sha256'],'monitor_sha256':m['monitor_sha256'],'e2_manifest_sha256':m['e2_manifest_sha256'],'output_dir':str(out),'expires_at_utc':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
 def check(v,yes):
  g.write_text(json.dumps(v));ok=True
  try:q.gate_check(g,m,out)
  except ValueError:ok=False
  assert ok==yes
 check(pins,True)
 class A: pass
 a=A();a.output=t/'already';a.output.mkdir();a.gate=g
 try:q.run(a,m,None,None,None,None,None,time.perf_counter());raise AssertionError('existing output dispatched')
 except ValueError as e:assert 'fresh output' in str(e)
 a.output=t/'fresh';g.write_text(json.dumps({**pins,'status':'pending'}))
 try:q.run(a,m,None,None,None,None,None,time.perf_counter());raise AssertionError('bad gate dispatched')
 except ValueError as e:assert 'gate' in str(e)
 for k,v in [('status','pending'),('scope','wrong'),('manifest_sha256','wrong'),('runner_sha256','wrong'),('holdout_runner_sha256','wrong'),('monitor_sha256','wrong'),('e2_manifest_sha256','wrong'),('output_dir',str(out/'wrong')),('expires_at_utc','2000-01-01T00:00:00Z')]:check({**pins,k:v},False)
 # Load the actual saved 097 no-E2 original, change only the new wrapper's field names.
 original=q.read(R/'output/bidirectional-holdout12-runtimefix-run-20260925/results/097-k5/online/solver.json');detail=copy.deepcopy(original['detail']);detail['fixed_owner_detail']=detail.pop('reverse_detail');detail['fixed_owner_error']=detail.pop('reverse_error');detail['skip_reason']='fixed_owner_construction_unavailable';base=detail['incumbent_detail']
 assert q.fixed_zero(detail,base)
 # Synthetic equality branch, using the saved zero-E2 ledger only as transport fixture.
 dup=copy.deepcopy(detail);dup.pop('fixed_owner_error');dup['skip_reason']='fixed_owner_duplicates_incumbent'
 dup['constructed_plans']=base['constructed_plans']+1
 base_dup=copy.deepcopy(base);base_dup['reason']='only_one_unique_plan';base_dup['construction_errors']=[]
 dup['incumbent_detail']=base_dup
 dup['fixed_owner_detail']={'selected':'fixed_owner_reverse','segment_count':1,'owner_split_count':0,
  'modeled_reverse_compute_finish':1,'modeled_reverse_op_starts':{},'modeled_split_cross_core_lags':{},
  'online_E0_calls':0,'scope':'synthetic'}
 assert q.fixed_duplicate(dup,base_dup)
 for path,value in [('skip_reason','wrong'),('selected','fixed_owner'),('reason','wrong'),('score_evidence','unknown'),
                    ('oracle_requests',1),('unique_scored_plans',1),('constructed_plans',base_dup['constructed_plans']),
                    ('fixed_owner_detail',None),('scores',{'x':[1,2]})]:
  x=copy.deepcopy(dup);x[path]=value;assert not q.fixed_duplicate(x,base_dup),path
 for key,value in [('score_evidence','unknown'),('unique_plans',2),('oracle_requests',1)]:
  b=copy.deepcopy(base_dup);b[key]=value;assert not q.fixed_duplicate(dup,b),key
 b=copy.deepcopy(base_dup);b['construction_errors']=[{'stage':'x','kind':'unexpected'}];assert not q.fixed_duplicate(dup,b)
 spec2=importlib.util.spec_from_file_location('hold',Path('/Users/nikolastar/.codex/worktrees/p2-fixed-owner-coverage9-20260925/huaweicup2026/scripts/q2_bidirectional_holdout.py'))
 hold=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(hold)
 hold.RAW_ROOT=Path('/Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/data/raw/a/official')
 hold.known_structural_unavailable=lambda x,b:q.fixed_zero(x,b) or q.fixed_duplicate(x,b)
 folder=t/'097-k5';(folder/'online').mkdir(parents=True);shutil.copyfile(R/'output/bidirectional-holdout12-runtimefix-run-20260925/results/097-k5/plan.json',folder/'plan.json')
 fixture=copy.deepcopy(original);fixture['detail']=dup
 sources={k:v for k,v in m['source_files'].items() if k.startswith('src/q2_nikolastarx/') and k.endswith('.py')}
 fixture['solver_source_sha256']={Path(k).name:v for k,v in sources.items()}
 (folder/'online/solver.json').write_text(json.dumps(fixture))
 process={'status':'ok','surviving_pids':[]}
 _,score,route=hold.inspect_solver(folder,'097',5,process,sources,{})
 assert score is None and route=='single_plan_independent_E0_only'
 bad=copy.deepcopy(fixture);bad['detail']['fixed_owner_detail']=None;(folder/'online/solver.json').write_text(json.dumps(bad))
 try:hold.inspect_solver(folder,'097',5,process,sources,{});raise AssertionError('bad duplicate accepted')
 except ValueError:pass
 for k,v in [('fixed_owner_error',"RuntimeError('unknown')"),('skip_reason','fixed_owner_score_unavailable'),('fixed_owner_detail',{}),('oracle_requests',1)]:
  bad=copy.deepcopy(detail);bad[k]=v;assert not q.fixed_zero(bad,base)
 badbase=copy.deepcopy(base);badbase['construction_errors'][0]['kind']='unexpected';assert not q.fixed_zero(detail,badbase)
 # A foreign cwd child only imports the adapter; it does not read a graph.
 code='import importlib.util,sys; p=sys.argv[1]; s=importlib.util.spec_from_file_location("foreign_cwd",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print("import-only-ok")'
 p=subprocess.run([m['python_invocation'],'-B','-c',code,str(H/'run.py')],cwd=t,capture_output=True,text=True,timeout=15)
 assert p.returncode==0 and p.stdout.strip()=='import-only-ok',p.stderr
 print(json.dumps({'status':'passed','negative_gate_cases':9,'wrong_output_and_gate_zero_dispatch':True,'097_positive_route':True,'097_rejected_variants':5,'duplicate_branch_positive':True,'duplicate_branch_field_rejections':13,'inspect_solver_replay':True,'foreign_cwd_import':True,'solver_calls':0,'E0_calls':0}))
