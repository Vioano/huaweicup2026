"""Single-use Colab controller; --execute is necessary, not an authorization grant."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,shutil,subprocess,sys,time
import select
HERE=pathlib.Path(__file__).resolve().parent
SESSION='p1-structural-two-cell-20260925'
BUNDLE_REMOTE='/content/two-cell-source-bundle.tar.gz'
ARCHIVE_REMOTE='/content/p1_structural_two_cell/evidence.tar.gz'
EMPTY='No active sessions found on server.'
def empty_sessions_receipt(receipt):
 """Accept only the two observed no-session messages, with optional final LF."""
 if type(receipt.get('returncode')) is not int or receipt['returncode']!=0 or receipt.get('stderr')!='':
  return False
 plain=EMPTY
 prefixed='[colab] '+EMPTY
 return receipt.get('stdout') in (plain,plain+'\n',prefixed,prefixed+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sources(pin):
 manifest=HERE/'artifact-manifest.json';raw=manifest.read_bytes()
 if sha(manifest)!=pin:raise ValueError('artifact manifest pin mismatch')
 locked=json.loads(raw)
 if locked.get('solver_commit')!='3a1b82b71ca1ff6689eb8e72f17d26c48b52073c' or locked.get('graphs',{}).get('case_016.json')!='76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef' or locked.get('graphs',{}).get('case_024.json')!='f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec':raise ValueError('artifact manifest identity mismatch')
 rows=locked.get('files')
 if not isinstance(rows,list) or len(rows)!=len({r.get('path') for r in rows}):raise ValueError('invalid artifact manifest')
 for row in rows:
  rel=pathlib.PurePosixPath(row['path'])
  if rel.is_absolute() or '..' in rel.parts or len(rel.parts)!=1:raise ValueError('unsafe artifact path')
  f=HERE/rel.name;b=f.read_bytes()
  if len(b)!=row['bytes'] or sha(f)!=row['sha256']:raise ValueError('artifact SHA/size mismatch: '+rel.name)
 required={'controller.py','controller_draft.py','remote_setup.py','two-cell-source-bundle.tar.gz','bundle-manifest.json'}
 if {r['path'] for r in rows}!=required:raise ValueError('artifact manifest coverage mismatch')
 return {'artifact_manifest_sha256':pin,'solver_commit':'3a1b82b71ca1ff6689eb8e72f17d26c48b52073c','graph_016_sha256':'76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef','graph_024_sha256':'f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec','artifacts_verified':len(rows)}

def actual_runner(label,argv,timeout):
 start=time.monotonic()
 try:
  p=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
  return {'step':label,'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'wall_seconds':time.monotonic()-start}
 except subprocess.TimeoutExpired as error:
  return {'step':label,'argv':argv,'returncode':None,'timeout_seconds':timeout,'stdout':str(error.stdout or ''),'stderr':str(error.stderr or ''),'wall_seconds':time.monotonic()-start}
def run_once(*,runner,watchdog_start,verify,now,persist,cli,artifact_manifest_sha256,session=SESSION,archive=None):
 archive=archive or HERE/'evidence.tar.gz'
 log={'status':'preflight','session':session,'source':sources(artifact_manifest_sha256),'steps':[],'VM_stopped_readback':False,'archive_collected':False,'e0_success':False}
 def save():persist(log)
 def invoke(label,tail,timeout):
  rec=runner(label,[cli,'--auth','oauth2',*tail],timeout);log['steps'].append(rec);save();return rec
 pre=invoke('preflight-sessions',['sessions'],10)
 if not empty_sessions_receipt(pre):
  log.update(status='preflight-failed',error='active or unreadable sessions');save();return log
 t0=now();deadline=t0+720;lease=t0+690;log['t0_monotonic']=t0;log['lease_deadline_monotonic']=lease;save()
 watchdog=watchdog_start(session,lease)
 attempted=False;download_attempted=False
 def bounded(label,tail,limit,reserve):
  if label in ('new','exec') and now()>=lease:raise TimeoutError(f'{label} refused after monotonic lease expiry')
  available=deadline-now()-reserve
  if available<1:raise TimeoutError(f'{label} lacks reserved stop/download time')
  return invoke(label,tail,min(limit,available))
 try:
  attempted=True
  r=bounded('new',['new','--session',session],25,680)
  if r.get('returncode')!=0:raise RuntimeError('VM creation unknown/failed')
  r=bounded('upload-bundle',['upload','--session',session,str(HERE/'two-cell-source-bundle.tar.gz'),BUNDLE_REMOTE],15,660)
  if r.get('returncode')!=0:raise RuntimeError('bundle upload failed')
  r=bounded('exec',['exec','--session',session,'--file',str(HERE/'remote_setup.py'),'--timeout','560'],560,100)
  if r.get('returncode')!=0:raise RuntimeError('remote setup/probe failed or unknown')
  download_attempted=True
  r=bounded('download',['download','--session',session,ARCHIVE_REMOTE,str(archive)],30,20)
  if r.get('returncode')!=0 or not archive.is_file():raise RuntimeError('evidence download failed')
  log['evidence']=verify(archive);log['archive_collected']=True;save()
  log['e0_success']=log['evidence'].get('status')=='complete' and log['evidence'].get('calls',{}).get('solver')==2 and log['evidence'].get('calls',{}).get('E0')==2
  log['status']='e0-success-collected' if log['e0_success'] else 'failed-e0-collected';save()
 except Exception as error:
  log.update(status='failed',error=f'{type(error).__name__}: {error}');save()
  if attempted and not download_attempted and not log['archive_collected'] and not archive.exists() and deadline-now()>45:
   try:
    download_attempted=True
    r=bounded('salvage-download',['download','--session',session,ARCHIVE_REMOTE,str(archive)],25,20)
    if r.get('returncode')==0 and archive.is_file():
     log['evidence']=verify(archive);log['archive_collected']=True;save()
   except Exception as salvage:
    log['salvage_error']=f'{type(salvage).__name__}: {salvage}';save()
 finally:
  if attempted:
   try:
    r=invoke('finally-stop',['stop','--session',session],min(12,max(1,deadline-now())))
    log['stop_returncode']=r.get('returncode')
   except Exception as error:log['stop_error']=f'{type(error).__name__}: {error}';save()
   try:
    r=invoke('finally-sessions',['sessions'],min(8,max(1,deadline-now())))
    log['VM_stopped_readback']=empty_sessions_receipt(r)
   except Exception as error:log['readback_error']=f'{type(error).__name__}: {error}';save()
  log['elapsed_seconds']=now()-t0
  if not log['VM_stopped_readback']:
   log['status']='stop-unconfirmed';log['e0_success']=False
  else:
   watchdog.cancel()
  save()
 return log
class Watchdog:
 def __init__(self,proc):self.proc=proc
 def cancel(self):
  if self.proc.poll() is None:self.proc.terminate();self.proc.wait(timeout=3)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--execute',action='store_true')
 p.add_argument('--watchdog',action='store_true')
 p.add_argument('--session',default=SESSION)
 p.add_argument('--cli',default=shutil.which('colab') or str(pathlib.Path.home()/'.local/bin/colab'))
 p.add_argument('--lease-deadline-monotonic',type=float)
 p.add_argument('--artifact-manifest-sha256',required=True)
 a=p.parse_args()
 cli=a.cli if pathlib.Path(a.cli).is_file() else None
 if a.watchdog:
  if not a.execute or not cli or a.lease_deadline_monotonic is None:raise SystemExit('watchdog requires --execute, CLI and monotonic deadline')
  if a.session!=SESSION:raise SystemExit('watchdog session mismatch')
  try: source=sources(a.artifact_manifest_sha256)
  except Exception as error:raise SystemExit(f'watchdog artifact verification failed: {error}')
  print(json.dumps({'ready':True,'pid':__import__('os').getpid(),'session':a.session,'deadline':a.lease_deadline_monotonic,'artifact_manifest_sha256':source['artifact_manifest_sha256']}),flush=True)
  while time.monotonic()<a.lease_deadline_monotonic:time.sleep(max(0,min(.25,a.lease_deadline_monotonic-time.monotonic())))
  stopped=actual_runner('watchdog-stop',[cli,'--auth','oauth2','stop','--session',a.session],12)
  readback=actual_runner('watchdog-sessions',[cli,'--auth','oauth2','sessions'],8)
  result={'stop':stopped,'sessions':readback,'VM_stopped_readback':empty_sessions_receipt(readback)}
  (HERE/'watchdog-stop.json').write_text(json.dumps(result,indent=2)+'\n')
  return
 if a.session!=SESSION:raise SystemExit('session must match frozen unique session')
 if not a.execute:raise SystemExit('explicit --execute required; resource grant is separate')
 if not cli:raise SystemExit('colab CLI unavailable')
 receipt=HERE/'controller-run.json'
 if receipt.exists() or (HERE/'evidence.tar.gz').exists():raise SystemExit('single-use outputs already exist')
 def persist(log):
  temp=receipt.with_suffix('.tmp');temp.write_text(json.dumps(log,indent=2)+'\n');temp.replace(receipt)
 def watchdog_start(session,deadline):
  proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--execute','--watchdog','--cli',cli,'--session',session,'--lease-deadline-monotonic',str(deadline),'--artifact-manifest-sha256',a.artifact_manifest_sha256],start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
  ready=select.select([proc.stdout],[],[],8)[0]
  if not ready:
   proc.terminate();proc.wait(timeout=3);raise RuntimeError('watchdog ready ACK timeout')
  ack=json.loads(proc.stdout.readline())
  if not ack.get('ready') or ack.get('session')!=session or ack.get('deadline')!=deadline or ack.get('artifact_manifest_sha256')!=a.artifact_manifest_sha256:
   proc.terminate();proc.wait(timeout=3);raise RuntimeError('watchdog ready ACK mismatch')
  armed={'session':session,'pid':proc.pid,'ready_ack':ack,'deadline_monotonic':deadline}
  (HERE/'watchdog-armed.json').write_text(json.dumps(armed,indent=2)+'\n')
  return Watchdog(proc)
 sources(a.artifact_manifest_sha256)
 from controller_draft import verify_evidence
 outcome=run_once(runner=actual_runner,watchdog_start=watchdog_start,verify=verify_evidence,now=time.monotonic,persist=persist,cli=cli,artifact_manifest_sha256=a.artifact_manifest_sha256,session=a.session)
 print(json.dumps({'status':outcome['status'],'archive_collected':outcome['archive_collected'],'VM_stopped_readback':outcome['VM_stopped_readback']}))
 if outcome['status']!='e0-success-collected':raise SystemExit(1)
if __name__=='__main__':main()
