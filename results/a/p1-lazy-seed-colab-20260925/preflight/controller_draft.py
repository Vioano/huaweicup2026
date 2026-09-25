"""Read-only CLI plan and evidence verifier; VM execution intentionally disabled.

A later reviewed controller must own session create/upload/exec/download and a
separate watchdog. This preparation file never invokes Colab.
"""
import argparse,hashlib,json,pathlib,tarfile
HERE=pathlib.Path(__file__).resolve().parent
BUNDLE=HERE/'lazy-seed-source-bundle.tar.gz'
def sha(data):return hashlib.sha256(data).hexdigest()
def verify_evidence(archive):
 with tarfile.open(archive,'r:gz') as tf:
  members=tf.getmembers();names=[m.name for m in members]
  if len(names)!=len(set(names)):raise ValueError('duplicate archive member')
  for m in members:
   p=pathlib.PurePosixPath(m.name)
   if not m.isfile() or not p.parts or p.is_absolute() or '..' in p.parts:raise ValueError('unsafe member')
  mname='evidence/evidence-manifest.json'
  if mname not in names:raise ValueError('missing evidence manifest')
  manifest=json.loads(tf.extractfile(mname).read());rows=manifest['files']
  if len(rows)!=len({r['path'] for r in rows}) or set(names)!={r['path'] for r in rows}|{mname}:raise ValueError('manifest coverage mismatch')
  contents={}
  for r in rows:
   data=tf.extractfile(r['path']).read()
   if len(data)!=r['bytes'] or sha(data)!=r['sha256']:raise ValueError('evidence hash mismatch: '+r['path'])
   contents[r['path']]=data
  setup=json.loads(contents['evidence/setup.json'])
  plan=contents.get('workspace/evidence/lazy-seed-008/plan.json')
  report=contents.get('workspace/evidence/lazy-seed-008/report.json')
  if setup.get('status')=='probe-complete':
   if plan is None or report is None:raise ValueError('successful receipt missing plan/report')
   parsed=json.loads(report)
   if parsed.get('status')!='verified_model' or parsed.get('plan_sha256')!=sha(plan):
    raise ValueError('downloaded plan/report identity mismatch')
  return {'archive_sha256':sha(archive.read_bytes()),'verified_files':len(rows),
          'setup_status':setup.get('status'),'plan_sha256_verified':setup.get('status')=='probe-complete'}
def plan():
 return {'status':'draft-no-VM-execution','source_bundle_sha256':sha(BUNDLE.read_bytes()),
         'remote_setup_sha256':sha((HERE/'remote_setup.py').read_bytes()),
         'session':'p1-lazy-seed-008-20260925','max_vm_lifetime_seconds':300,
         'steps':['read sessions and require no active session','start independent <=295s stop watchdog',
                  'create one Standard CPU VM','upload fixed bundle and remote_setup.py',
                  'exec remote_setup.py once with bounded timeout','download evidence.tar.gz bytes',
                  'verify safe members and every size/SHA','finally stop owned session and read sessions'],
         'limits':{'process_wall_seconds':45,'process_address_space_bytes':536870912,
                   'constructor_wall_seconds':30,'Task_compile':20,'Fraction_response':3,
                   'oracle_queries':2,'E0':0,'E1':0,'E2':0,'retry':0},
         'execution_enabled':False}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--show-plan',action='store_true')
 p.add_argument('--verify-evidence',type=pathlib.Path)
 p.add_argument('--execute',action='store_true')
 a=p.parse_args()
 if a.execute:raise SystemExit('VM execution is disabled pending supervisor review')
 if a.verify_evidence:print(json.dumps(verify_evidence(a.verify_evidence)))
 else:print(json.dumps(plan(),indent=2))
if __name__=='__main__':main()
