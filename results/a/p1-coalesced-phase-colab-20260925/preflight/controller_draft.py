"""Strict coalesced phase evidence verifier; success means one paired model run, never E0."""
import hashlib,json,pathlib,tarfile
HERE=pathlib.Path(__file__).resolve().parent
GRAPH='c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d'
def sha(b):return hashlib.sha256(b).hexdigest()
def verify_evidence(archive):
 with tarfile.open(archive,'r:gz') as tf:
  ms=tf.getmembers();names=[m.name for m in ms]
  if len(names)!=len(set(names)):raise ValueError('duplicate archive member')
  for m in ms:
   p=pathlib.PurePosixPath(m.name)
   if not m.isfile() or not p.parts or p.is_absolute() or '..' in p.parts:raise ValueError('unsafe archive member')
  mn='evidence/evidence-manifest.json'
  if mn not in names:raise ValueError('missing evidence manifest')
  rows=json.loads(tf.extractfile(mn).read())['files']
  if len(rows)!=len({x['path'] for x in rows}) or set(names)!={x['path'] for x in rows}|{mn}:raise ValueError('manifest coverage mismatch')
  data={}
  for row in rows:
   b=tf.extractfile(row['path']).read()
   if len(b)!=row['bytes'] or sha(b)!=row['sha256']:raise ValueError('evidence hash mismatch: '+row['path'])
   data[row['path']]=b
  setup=json.loads(data['evidence/setup.json'])
  dp='workspace/evidence/coalesced-008-k5/diagnostics.json'
  cp='workspace/evidence/coalesced-008-k5/control-plan.json';pp='workspace/evidence/coalesced-008-k5/phase-plan.json'
  if any(x not in data for x in (dp,cp,pp)):raise ValueError('missing paired diagnostics or plans')
  d=json.loads(data[dp]);control=json.loads(data[cp]);phase=json.loads(data[pp])
  if setup.get('status')!='phase-pair-complete-NOT-E0' or d.get('status')!='model_pair_complete_NOT_E0':raise ValueError('run did not complete paired model probe')
  if d.get('graph_sha256')!=GRAPH:raise ValueError('graph SHA mismatch')
  calls=d.get('calls',{})
  if calls.get('Task_compile_confirmed')!=27 or calls.get('Fraction_attempts')!=2:raise ValueError('Task/Fraction call count mismatch')
  if any(calls.get(k)!=0 for k in ('E0','E1','E2','retry')):raise ValueError('unauthorized score/retry call recorded')
  if not all(isinstance(d.get(k),dict) and isinstance(d[k].get('trace'),list) for k in ('control_model','phase_model')):raise ValueError('both keep_trace model results required')
  expected={'node_to_subgraph','core_schedules'}
  if set(control)!=expected or set(phase)!=expected or control['node_to_subgraph']!=phase['node_to_subgraph']:raise ValueError('two-key plans or shared partition mismatch')
  return {'archive_sha256':sha(archive.read_bytes()),'verified_files':len(rows),'setup_status':setup['status'],'diagnostics_verified':True,'diagnostics_status':d['status'],'graph_sha256':GRAPH,'Task_compile_confirmed':27,'Fraction_attempts':2,'E0':0,'E1':0,'E2':0,'retry':0,'both_traces':True,'same_partition':True}
