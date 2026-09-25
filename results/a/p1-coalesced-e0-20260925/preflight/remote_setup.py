"""Pending pinned E0-only remote wrapper; never invokes a solver or batch CLI."""
import hashlib,json,os,pathlib,posixpath,resource,signal,subprocess,tarfile,time
BASE=pathlib.Path('/content/p1_coalesced_e0_window');BUNDLE=pathlib.Path('/content/coalesced-e0-source-bundle.tar.gz')
WS=BASE/'workspace';EVID=BASE/'evidence';TARGET=WS/'run-first-e0'
BUNDLE_SHA='322240ba7c328c20f3cae21fc0e463ff78b3ed9101eb673101e24d431024d154'
PLAN_SHA='e9327269bc95a81d17ca907a617aed896fd6fdde2a3174044d975f746569f9ce';GRAPH_SHA='c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d'
def sha(b):return hashlib.sha256(b).hexdigest()
def proc_start(pid):
 try:return int(pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[19])
 except (OSError,ValueError,IndexError):return None
def kill_e0(attempt):
 ident=attempt.get('process_identity') or {};pid=ident.get('pid');pgid=ident.get('pgid');start=ident.get('linux_proc_start_ticks')
 if type(pid)is not int or type(pgid)is not int or type(start)is not int or pid<=1 or pid!=pgid:return {'identity_valid':False,'killed':False,'exited':False}
 try:
  current=proc_start(pid)
  if current is None:return {'identity_valid':True,'killed':False,'exited':True,'residual':False}
  if current!=start:return {'identity_valid':True,'killed':False,'exited':True,'residual':False,'pid_reused':True}
  if os.getpgid(pid)!=pgid:return {'identity_valid':False,'killed':False,'exited':False,'residual':True}
  os.killpg(pgid,signal.SIGKILL)
 except ProcessLookupError:return {'identity_valid':True,'killed':False,'exited':True,'residual':False,'exit_race':True}
 except PermissionError:return {'identity_valid':True,'killed':False,'exited':False,'residual':True,'permission_error':True}
 limit=time.monotonic()+8
 while time.monotonic()<limit and proc_start(pid)==start:time.sleep(.05)
 residual=proc_start(pid)==start
 return {'identity_valid':True,'killed':True,'exited':not residual,'residual':residual}
def read_attempt():
 try:return json.loads((TARGET/'attempt.json').read_text())
 except (OSError,ValueError):return {}
def main():
 record={'status':'started','calls':{'E0':0,'solver':0,'E1':0,'E2':0,'retry':0}}
 proc=None;BASE.mkdir(parents=True,exist_ok=False);EVID.mkdir()
 try:
  record['remote_started_monotonic']=time.monotonic();overall=record['remote_started_monotonic']+220;record['remote_deadline_monotonic']=overall
  raw=BUNDLE.read_bytes();assert BUNDLE_SHA!='PENDING_FIXED_RUNNER_COMMIT' and sha(raw)==BUNDLE_SHA
  with tarfile.open(BUNDLE,'r:gz') as tf:
   ms=tf.getmembers();names=[m.name for m in ms];assert len(names)==len(set(names))
   for m in ms:
    q=pathlib.PurePosixPath(m.name);assert m.isfile() and q.parts and not q.is_absolute() and '..' not in q.parts
   bm=json.loads(tf.extractfile('bundle-manifest.json').read());assert bm['data_head']=='a008dfb8f1b5b881844af312be0b7246b2c6b025' and bm['plan_sha256']==PLAN_SHA and bm['graph_sha256']==GRAPH_SHA
   assert set(names)=={x['path'] for x in bm['files']}|{'bundle-manifest.json'};WS.mkdir()
   for x in bm['files']:
    b=tf.extractfile(x['path']).read();assert len(b)==x['bytes'] and sha(b)==x['sha256']
    dst=WS/x['path'];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
  assert sha((WS/'phase-plan.json').read_bytes())==PLAN_SHA and sha((WS/'case_008.json').read_bytes())==GRAPH_SHA
  sm=json.loads((WS/'docs/a/source-manifest.json').read_text());smfiles={x['path']:x for x in sm['files']}
  for rel,row in smfiles.items():
   if rel.startswith('code/') or rel=='data/config.txt':
    b=(WS/'data/raw/a/official'/rel).read_bytes();assert len(b)==row['bytes'] and sha(b)==row['sha256']
  agg=hashlib.sha256()
  for rel,row in sorted(smfiles.items()):
   if rel.startswith('code/'):agg.update(rel.encode()+b'\t'+row['sha256'].encode()+b'\n')
  assert agg.hexdigest()==sm['official_code_hash']=='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
  uv=subprocess.run(['python3','-m','pip','show','uv'],capture_output=True,text=True,timeout=min(8,max(.1,overall-time.monotonic()-130)))
  if uv.returncode:
   install=subprocess.run(['python3','-m','pip','install','uv'],capture_output=True,text=True,timeout=min(35,max(.1,overall-time.monotonic()-130)));record['uv_install']={'returncode':install.returncode,'stdout':install.stdout[-1000:],'stderr':install.stderr[-1000:]};assert install.returncode==0
  sync_budget=min(100,overall-time.monotonic()-130);assert sync_budget>1,'insufficient remote time for dependency sync and E0';record['uv_sync']={'argv':['uv','sync','--locked','--python','3.12.13'],'timeout_seconds':sync_budget};u=subprocess.run(['uv','sync','--locked','--python','3.12.13'],cwd=WS,capture_output=True,text=True,timeout=sync_budget);record['uv_sync'].update(returncode=u.returncode,stdout=u.stdout[-2000:],stderr=u.stderr[-2000:]);assert u.returncode==0
  env=os.environ.copy();env.update(PYTHONPATH='.:data/raw/a/official/code',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
  assert overall-time.monotonic()>=70,'refuse E0 without 60s child plus cleanup reserve';deadline=min(overall,time.monotonic()+120);assert not TARGET.exists(),'single-use runner output already exists'
  argv=['.venv/bin/python','-B','-m','src.review.p1_saved_plan_e0_once','--graph',str(WS/'case_008.json'),'--plan',str(WS/'phase-plan.json'),'--output-dir',str(TARGET),'--deadline-monotonic',str(deadline),'--execute'];record.update(runner_argv=argv,stage='e0-runner')
  with (EVID/'runner.stdout').open('xb') as so,(EVID/'runner.stderr').open('xb') as se:
   proc=subprocess.Popen(argv,cwd=WS,env=env,start_new_session=True,stdout=so,stderr=se);runner_start=proc_start(proc.pid)
   try:rc=proc.wait(timeout=max(.1,deadline-time.monotonic()))
   except subprocess.TimeoutExpired:
    record['outer_timeout']=True;record['e0_child_cleanup']=kill_e0(read_attempt())
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    rc=proc.wait(timeout=8)
   record['runner_returncode']=rc;record['runner_starttime']=runner_start
  attempt=read_attempt()
  record['calls']['E0']=attempt.get('calls',{}).get('E0',0);record['e0_attempt']=attempt
  record['status']='e0-complete' if rc==0 and attempt.get('state')=='ok' and attempt.get('cleanup_confirmed') is True and record['calls']['E0']==1 else 'e0-failed-artifacts-preserved'
 except Exception as e:record.update(status='setup-or-runner-failed',error=f'{type(e).__name__}: {e}')
 finally:
  try:
   attempt=read_attempt();cleanup=kill_e0(attempt);record['finally_e0_cleanup']=cleanup
   if proc is not None and proc.poll() is None:
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    try:proc.wait(timeout=8)
    except subprocess.TimeoutExpired:record['runner_residual']=True
   record['runner_exited']=proc is None or proc.poll() is not None
   record['e0_residual_confirmed_absent']=cleanup.get('exited') is True
   record['peak_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
   if record.get('status')=='e0-complete' and (not record['runner_exited'] or not record['e0_residual_confirmed_absent']):record['status']='e0-failed-artifacts-preserved'
  except Exception as cleanup_error:record['cleanup_error']=f'{type(cleanup_error).__name__}: {cleanup_error}'
  record['finished_monotonic']=time.monotonic();record['remote_wall_seconds']=record['finished_monotonic']-record.get('remote_started_monotonic',record['finished_monotonic'])
  (EVID/'setup.json').write_text(json.dumps(record,indent=2)+'\n')
  files=[x for r in (EVID,TARGET) if r.exists() for x in r.rglob('*') if x.is_file()];rows=[{'path':x.relative_to(BASE).as_posix(),'bytes':x.stat().st_size,'sha256':sha(x.read_bytes())} for x in sorted(files)]
  (EVID/'evidence-manifest.json').write_text(json.dumps({'files':rows},indent=2)+'\n')
  with tarfile.open(BASE/'evidence.tar.gz','w:gz') as tf:
   for x in sorted(files+[EVID/'evidence-manifest.json']):tf.add(x,arcname=x.relative_to(BASE).as_posix(),recursive=False)
 print(json.dumps({'status':record['status'],'E0':record['calls']['E0'],'archive_sha256':sha((BASE/'evidence.tar.gz').read_bytes())}))
if __name__=='__main__':main()
