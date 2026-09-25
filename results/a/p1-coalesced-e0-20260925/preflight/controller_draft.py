"""Verify a single frozen E0 archive without initiating any evaluation."""
import hashlib,json,pathlib,tarfile
PLAN_SHA='e9327269bc95a81d17ca907a617aed896fd6fdde2a3174044d975f746569f9ce'
GRAPH_SHA='c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d'
def sha(b):return hashlib.sha256(b).hexdigest()
def verify_evidence(archive):
 with tarfile.open(archive,'r:gz') as tf:
  ms=tf.getmembers();names=[m.name for m in ms]
  if len(names)!=len(set(names)):raise ValueError('duplicate archive member')
  for m in ms:
   q=pathlib.PurePosixPath(m.name)
   if not m.isfile() or not q.parts or q.is_absolute() or '..' in q.parts:raise ValueError('unsafe member')
  mn='evidence/evidence-manifest.json'
  rows=json.loads(tf.extractfile(mn).read())['files']
  if set(names)!={x['path'] for x in rows}|{mn}:raise ValueError('manifest coverage mismatch')
  data={}
  for row in rows:
   b=tf.extractfile(row['path']).read()
   if len(b)!=row['bytes'] or sha(b)!=row['sha256']:raise ValueError('evidence hash mismatch')
   data[row['path']]=b
  setup=json.loads(data['evidence/setup.json'])
  if setup.get('status')!='e0-complete' or setup.get('calls',{}).get('E0')!=1 or setup.get('e0_residual_confirmed_absent') is not True or setup.get('runner_exited') is not True:raise ValueError('E0 completion or process cleanup not confirmed')
  if any(setup.get('calls',{}).get(k)!=0 for k in ('solver','E1','E2','retry')):raise ValueError('unexpected solver/score/retry')
  attempt=json.loads(data['workspace/run-first-e0/attempt.json'])
  ident=attempt.get('identity',{})
  if attempt.get('state')!='ok' or attempt.get('cleanup_confirmed') is not True or attempt.get('calls',{}).get('E0')!=1 or attempt.get('calls',{}).get('constructor')!=0:raise ValueError('attempt state/call ledger/cleanup mismatch')
  if ident.get('plan_sha256')!=PLAN_SHA or ident.get('graph_sha256')!=GRAPH_SHA:raise ValueError('identity mismatch')
  needed=['workspace/run-first-e0/result.json','workspace/run-first-e0/trace.json','workspace/run-first-e0/official.log','workspace/run-first-e0/E0.stdout.txt','workspace/run-first-e0/E0.stderr.txt','workspace/run-first-e0/E0.stdout.raw.txt','workspace/run-first-e0/E0.stderr.raw.txt']
  if any(x not in data for x in needed):raise ValueError('missing raw E0 artifacts')
  return {'archive_sha256':sha(archive.read_bytes()),'verified_files':len(rows),'e0_status':'ok','plan_sha256':PLAN_SHA,'graph_sha256':GRAPH_SHA,'E0':1,'solver':0,'E1':0,'E2':0,'retry':0}
