"""Single-use Colab controller; --execute is necessary, not an authorization grant."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,shutil,subprocess,sys,time
from controller_draft import verify_evidence
HERE=pathlib.Path(__file__).resolve().parent
SESSION='p1-period7-008-20260925'
REMOTE_SHA='ec09c2b5ff23428ca7df0791c6a9c3d6d600bd29d165764c342983664f5dbb22'
BUNDLE_REMOTE='/content/p1-period7-source-bundle.tar.gz'
ARCHIVE_REMOTE='/content/p1_period7_window/evidence.tar.gz'
EMPTY='No active sessions found on server.'
def empty_sessions_receipt(receipt):
 """Accept only the two observed no-session messages, with optional final LF."""
 if type(receipt.get('returncode')) is not int or receipt['returncode']!=0 or receipt.get('stderr')!='':
  return False
 plain=EMPTY
 prefixed='[colab] '+EMPTY
 return receipt.get('stdout') in (plain,plain+'\n',prefixed,prefixed+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sources():
 receipt=json.loads((HERE/'offline-check.json').read_text())
 if receipt.get('status')!='offline-checked' or receipt.get('source_commit')!='030f2b8aff4dc5e6b1acf9d88dc4984e54f1b5fa':raise ValueError('wrong source receipt')
 if sha(HERE/'period7-source-bundle.tar.gz')!=receipt['bundle_sha256'] or sha(HERE/'bundle-manifest.json')!=receipt['manifest_sha256'] or sha(HERE/'remote_setup.py')!=REMOTE_SHA:raise ValueError('source bundle/manifest/remote SHA mismatch')
 if receipt.get('remote_setup_sha256')!=REMOTE_SHA:raise ValueError('remote script absent from frozen receipt')
 return {'bundle_sha256':receipt['bundle_sha256'],'manifest_sha256':receipt['manifest_sha256'],'remote_sha256':REMOTE_SHA,'controller_sha256':sha(pathlib.Path(__file__)),'verifier_sha256':sha(HERE/'controller_draft.py')}
def actual_runner(label,argv,timeout):
 start=time.monotonic()
 try:
  p=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
  return {'step':label,'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'wall_seconds':time.monotonic()-start}
 except subprocess.TimeoutExpired as error:
  return {'step':label,'argv':argv,'returncode':None,'timeout_seconds':timeout,'stdout':str(error.stdout or ''),'stderr':str(error.stderr or ''),'wall_seconds':time.monotonic()-start}
def run_once(*,runner,watchdog_start,verify,now,persist,cli,session=SESSION,archive=None):
 archive=archive or HERE/'evidence.tar.gz'
 log={'status':'preflight','session':session,'source':sources(),'steps':[],'VM_stopped_readback':False,'archive_collected':False,'probe_success':False}
 def save():persist(log)
 def invoke(label,tail,timeout):
  rec=runner(label,[cli,'--auth','oauth2',*tail],timeout);log['steps'].append(rec);save();return rec
 pre=invoke('preflight-sessions',['sessions'],10)
 if not empty_sessions_receipt(pre):
  log.update(status='preflight-failed',error='active or unreadable sessions');save();return log
 t0=now();deadline=t0+300;log['t0_monotonic']=t0;save()
 watchdog=watchdog_start(session,t0+270)
 attempted=False;download_attempted=False
 def bounded(label,tail,limit,reserve):
  available=deadline-now()-reserve
  if available<1:raise TimeoutError(f'{label} lacks reserved stop/download time')
  return invoke(label,tail,min(limit,available))
 try:
  attempted=True
  r=bounded('new',['new','--session',session],50,225)
  if r.get('returncode')!=0:raise RuntimeError('VM creation unknown/failed')
  r=bounded('upload-bundle',['upload','--session',session,str(HERE/'period7-source-bundle.tar.gz'),BUNDLE_REMOTE],25,200)
  if r.get('returncode')!=0:raise RuntimeError('bundle upload failed')
  r=bounded('exec',['exec','--session',session,'--file',str(HERE/'remote_setup.py'),'--timeout','145'],155,45)
  if r.get('returncode')!=0:raise RuntimeError('remote setup/probe failed or unknown')
  download_attempted=True
  r=bounded('download',['download','--session',session,ARCHIVE_REMOTE,str(archive)],25,20)
  if r.get('returncode')!=0 or not archive.is_file():raise RuntimeError('evidence download failed')
  log['evidence']=verify(archive);log['archive_collected']=True;save()
  log['probe_success']=log['evidence'].get('setup_status')=='probe-complete' and log['evidence'].get('plan_sha256_verified') is True
  log['status']='probe-success-collected' if log['probe_success'] else 'failed-probe-collected';save()
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
   log['status']='stop-unconfirmed';log['probe_success']=False
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
 p.add_argument('--deadline-epoch',type=float)
 a=p.parse_args()
 cli=a.cli if pathlib.Path(a.cli).is_file() else None
 if a.watchdog:
  if not a.execute or not cli or a.deadline_epoch is None:raise SystemExit('watchdog requires --execute, CLI and deadline')
  time.sleep(max(0,a.deadline_epoch-time.time()))
  result=actual_runner('watchdog-stop',[cli,'--auth','oauth2','stop','--session',a.session],12)
  (HERE/'watchdog-stop.json').write_text(json.dumps(result,indent=2)+'\n')
  return
 if not a.execute:raise SystemExit('explicit --execute required; resource grant is separate')
 if not cli:raise SystemExit('colab CLI unavailable')
 receipt=HERE/'controller-run.json'
 if receipt.exists() or (HERE/'evidence.tar.gz').exists():raise SystemExit('single-use outputs already exist')
 def persist(log):
  temp=receipt.with_suffix('.tmp');temp.write_text(json.dumps(log,indent=2)+'\n');temp.replace(receipt)
 def watchdog_start(session,deadline):
  proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--execute','--watchdog','--cli',cli,'--session',session,'--deadline-epoch',str(time.time()+max(0,deadline-time.monotonic()))],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return Watchdog(proc)
 outcome=run_once(runner=actual_runner,watchdog_start=watchdog_start,verify=verify_evidence,now=time.monotonic,persist=persist,cli=cli,session=a.session)
 print(json.dumps({'status':outcome['status'],'archive_collected':outcome['archive_collected'],'VM_stopped_readback':outcome['VM_stopped_readback']}))
 if outcome['status']!='probe-success-collected':raise SystemExit(1)
if __name__=='__main__':main()
