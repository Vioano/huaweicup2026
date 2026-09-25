"""Verify two-cell evidence without dispatching work."""
import hashlib,json,pathlib,tarfile
GRAPH={'016':'76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef','024':'f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec'}
def sha(b):return hashlib.sha256(b).hexdigest()
def verify_evidence(path):
 with tarfile.open(path,'r:gz') as t:
  ms=t.getmembers();names=[m.name for m in ms]
  if len(names)!=len(set(names)) or any(not m.isfile() or pathlib.PurePosixPath(m.name).is_absolute() or '..' in pathlib.PurePosixPath(m.name).parts for m in ms):raise ValueError('unsafe evidence archive')
  mani='evidence/evidence-manifest.json';rows=json.loads(t.extractfile(mani).read())['files']
  if set(names)!={r['path'] for r in rows}|{mani}:raise ValueError('archive manifest coverage mismatch')
  data={}
  for r in rows:
   b=t.extractfile(r['path']).read()
   if len(b)!=r['bytes'] or sha(b)!=r['sha256']:raise ValueError('evidence bytes mismatch')
   data[r['path']]=b
  setup=json.loads(data['evidence/setup.json']);a=json.loads(data['workspace/two-cell-run/attempt.json'])
  if setup.get('status')!='complete' or setup.get('runner_exit')!=0 or setup.get('adopted_cleanup',{}).get('confirmed') is not True or setup.get('runner_exited') is not True or setup.get('stage_child_cleanup',{}).get('confirmed') is not True or a.get('status')!='complete' or a.get('worker_cleanup',{}).get('confirmed') is not True:raise ValueError('run/cleanup incomplete')
  c=a.get('calls',{})
  if c.get('solver')!=2 or c.get('E0')!=2 or type(c.get('E1')) is not int or c['E1']>18 or c.get('E2')!=0 or c.get('retry')!=0:raise ValueError('call ledger outside frozen budget')
  cells={x['case']:x for x in a.get('cells',[])}
  if set(cells)!=set(GRAPH):raise ValueError('cell coverage mismatch')
  if c['E1']!=sum(x.get('calls',{}).get('E1',-1) for x in cells.values()):raise ValueError('aggregate E1 does not equal cell ledger')
  for case,digest in GRAPH.items():
   x=cells[case]
   for stage in ('solver','evaluation'):
    proc=x.get(stage,{})
    ident=proc.get('process_identity',{})
    if proc.get('status')!='ok' or proc.get('exit_code')!=0 or proc.get('cleanup_confirmed') is not True or proc.get('adopted_cleanup',{}).get('confirmed') is not True:raise ValueError('stage execution/cleanup unconfirmed')
    if any(type(ident.get(k)) is not int or ident[k]<=0 for k in ('pid','pgid','linux_proc_start_ticks')) or ident['pid']!=ident['pgid']:raise ValueError('stage process identity unavailable')
   if x.get('status')!='ok' or x.get('graph_sha256')!=digest or x.get('calls')!={'solver':1,'E1':x.get('calls',{}).get('E1'),'E0':1} or type(x['calls']['E1']) is not int or not 0<=x['calls']['E1']<=9:raise ValueError('cell identity/calls mismatch')
   if x.get('calls',{}).get('E1')!=json.loads(data[f'workspace/two-cell-run/{case}/diagnostics.json']).get('actual_e1_calls_total'):raise ValueError('diagnostic E1 counter mismatch')
   base=f'workspace/two-cell-run/{case}/'
   diag=json.loads(data[base+'diagnostics.json']);plan_path=base+f'case_{case}_multicore_res.json'
   if plan_path not in data or sha(data[plan_path])!=x.get('plan_sha256') or diag.get('selected_plan_sha256')!=x.get('plan_sha256'):raise ValueError('solver plan/diagnostic identity mismatch')
   result=json.loads(data[base+'result.json'])
   if result.get('scene')!='A' or result.get('num_cores')!=5 or result.get('makespan')!=x.get('makespan_cycles'):raise ValueError('E0 result identity or makespan mismatch')
   for leaf in (f'case_{case}_multicore_res.json','diagnostics.json','result.json','trace.json','official.log','solver.stdout.txt','solver.stderr.txt','solver.stdout.raw.txt','solver.stderr.raw.txt','E0.stdout.txt','E0.stderr.txt','E0.stdout.raw.txt','E0.stderr.raw.txt'):
    if base+leaf not in data:raise ValueError('missing cell evidence '+leaf)
  return {'status':'complete','calls':c,'cells':sorted(cells),'verified_files':len(rows),'archive_sha256':sha(pathlib.Path(path).read_bytes())}
