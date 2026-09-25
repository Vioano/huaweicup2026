"""Fake-only tests for lease refusal, artifact pinning and detached watchdog recovery."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import controller
PIN=hashlib.sha256((HERE/'artifact-manifest.json').read_bytes()).hexdigest()
FILES=['controller.py','controller_draft.py','remote_setup.py','coalesced-e0-source-bundle.tar.gz','bundle-manifest.json','artifact-manifest.json']
def clone_runtime(dst):
 for n in FILES:shutil.copy2(HERE/n,dst/n)
def fake_cli(path,log):
 path.write_text('#!/usr/bin/env python3\nimport json,os,sys\nwith open(os.environ["FAKE_LOG"],"a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\nif sys.argv[-1]=="sessions":print("[colab] No active sessions found on server.")\n')
 path.chmod(0o755)
def lease_expiry_blocks_exec_but_cleans_up():
 t=[100.];events=[]
 class WD:
  def cancel(self):events.append('cancel')
 def runner(label,argv,timeout):
  events.append(label)
  if label in ('preflight-sessions','finally-sessions'):return {'returncode':0,'stdout':'[colab] No active sessions found on server.\n','stderr':''}
  if label=='upload-bundle':t[0]=701.
  return {'returncode':0,'stdout':'','stderr':''}
 with tempfile.TemporaryDirectory() as td:
  r=controller.run_once(runner=runner,watchdog_start=lambda *_:WD(),verify=lambda _: {},now=lambda:t[0],persist=lambda _:None,cli='/fake/colab',artifact_manifest_sha256=PIN,archive=pathlib.Path(td)/'e.tar.gz')
 assert 'new' in events and 'upload-bundle' in events and 'exec' not in events
 assert 'finally-stop' in events and 'finally-sessions' in events

def parent_crash_watchdog_only_stops_its_frozen_session():
 with tempfile.TemporaryDirectory() as td:
  d=pathlib.Path(td);clone_runtime(d);log=d/'calls.jsonl';cli=d/'fake-colab';fake_cli(cli,log)
  launcher=d/'launcher.py';launcher.write_text('''import json,os,pathlib,subprocess,sys\nd,cli,log,deadline,pin=sys.argv[1:]\np=subprocess.Popen([sys.executable,str(pathlib.Path(d)/"controller.py"),"--execute","--watchdog","--cli",cli,"--session","p1-coalesced-e0-008-k5-20260925","--lease-deadline-monotonic",deadline,"--artifact-manifest-sha256",pin],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True)\nack=json.loads(p.stdout.readline());assert ack["ready"] and ack["session"]=="p1-coalesced-e0-008-k5-20260925"\npathlib.Path(d,"watchdog.pid").write_text(str(p.pid));os._exit(17)\n''')
  deadline=time.monotonic()+.5;env=os.environ.copy();env['FAKE_LOG']=str(log)
  parent=subprocess.run([sys.executable,str(launcher),td,str(cli),str(log),str(deadline),PIN],env=env,timeout=5)
  assert parent.returncode==17
  pid=int((d/'watchdog.pid').read_text())
  until=time.monotonic()+6;receipt=d/'watchdog-stop.json'
  def exited(pid):
   q=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True)
   return not q.stdout.strip() or q.stdout.strip().startswith('Z')
  while time.monotonic()<until and (not receipt.exists() or not exited(pid)):time.sleep(.05)
  assert receipt.exists(),'watchdog stop/readback receipt was not completed'
  assert exited(pid),'watchdog process did not exit'
  watchdog_result=json.loads(receipt.read_text());assert watchdog_result['VM_stopped_readback'] is True
  calls=[json.loads(x) for x in log.read_text().splitlines()]
  stops=[x for x in calls if 'stop' in x]
  assert stops==[['--auth','oauth2','stop','--session','p1-coalesced-e0-008-k5-20260925']]
  assert ['--auth','oauth2','sessions'] in calls
  try:os.kill(pid,0)
  except ProcessLookupError:pass
  else:raise AssertionError('detached watchdog did not exit')

def altered_verifier_fails_before_cli():
 with tempfile.TemporaryDirectory() as td:
  d=pathlib.Path(td);clone_runtime(d);v=d/'controller_draft.py';v.write_bytes(v.read_bytes()+b'\n')
  log=d/'calls.jsonl';cli=d/'fake-colab';fake_cli(cli,log);env=os.environ.copy();env['FAKE_LOG']=str(log)
  r=subprocess.run([sys.executable,str(d/'controller.py'),'--execute','--cli',str(cli),'--artifact-manifest-sha256',PIN],env=env,capture_output=True,text=True,timeout=5)
  assert r.returncode!=0 and not log.exists()
def failed_download_salvage_preserves_bytes_on_semantic_rejection():
 payload=b'raw diagnostic archive'
 with tempfile.TemporaryDirectory() as td:
  archive=pathlib.Path(td)/'evidence.tar.gz';events=[]
  class WD:
   def cancel(self):pass
  def runner(label,argv,timeout):
   events.append(label)
   if label in ('preflight-sessions','finally-sessions'):return {'returncode':0,'stdout':'No active sessions found on server.','stderr':''}
   if label=='exec':return {'returncode':1,'stdout':'','stderr':'runner failed before archive transfer'}
   if label=='salvage-download':archive.write_bytes(payload);return {'returncode':0,'stdout':'','stderr':''}
   return {'returncode':0,'stdout':'','stderr':''}
  def reject(_):raise ValueError('archive semantics rejected')
  result=controller.run_once(runner=runner,watchdog_start=lambda *_:WD(),verify=reject,now=time.monotonic,persist=lambda _:None,cli='/fake/colab',artifact_manifest_sha256=PIN,archive=archive)
  assert result['archive_collected'] is False and archive.read_bytes()==payload
  assert 'salvage-download' in events and 'finally-stop' in events and 'finally-sessions' in events
if __name__=='__main__':
 try:controller.sources('0'*64);raise AssertionError('bad manifest pin accepted')
 except ValueError:pass
 lease_expiry_blocks_exec_but_cleans_up();parent_crash_watchdog_only_stops_its_frozen_session();altered_verifier_fails_before_cli();failed_download_salvage_preserves_bytes_on_semantic_rejection()
 print(json.dumps({'expired_lease_refuses_exec_and_cleans_up':True,'launcher_parent_exited_17':True,'detached_watchdog_stop_session_count':1,'tampered_verifier_refused_before_cli':True,'failed_download_raw_bytes_preserved':True}))
