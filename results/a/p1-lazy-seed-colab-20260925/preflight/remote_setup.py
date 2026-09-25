"""Single-use Colab setup/probe. Draft only; no local invocation in preparation."""
import gzip,hashlib,io,json,os,pathlib,resource,signal,subprocess,sys,tarfile,time
BASE=pathlib.Path('/content/p1_lazy_seed_window');BUNDLE=pathlib.Path('/content/p1-lazy-seed-source-bundle.tar.gz')
WS=BASE/'workspace'; EVID=BASE/'evidence'; TARGET=WS/'evidence/lazy-seed-008'
BUNDLE_SHA='b78c67f1c535625ac6ff31545b179cb2a5bfcd1f762fff99248d9364c7101ab9'
MANIFEST_SHA='bab142222b94ee7f39df1b6394f03c4f071538b4f723b3a213c951e85ecb906a'
COMMAND=['.venv/bin/python','-B','-m','src.review.p1_lazy_memory_probe','case_008.json','--cores','5','--capacity-l1','524288','--capacity-ub','131072','--bandwidth','60','--gate','100','--task-limit','20','--final-max-tasks','10','--response-limit','3','--oracle-limit','2','--expansion-limit','10','--seconds','30','--output-root','evidence/lazy-seed-008','--execute']
def sha(b):return hashlib.sha256(b).hexdigest()
def utc():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def cmd(argv,timeout,cwd=None):
 t=time.monotonic();p=subprocess.run(argv,cwd=cwd,text=True,capture_output=True,timeout=timeout)
 return {'argv':argv,'returncode':p.returncode,'wall_seconds':time.monotonic()-t,'stdout':p.stdout,'stderr':p.stderr}
def owned(pgid):
 found=[]
 for p in pathlib.Path('/proc').iterdir():
  if p.name.isdecimal():
   try:
    if os.getpgid(int(p.name))==pgid:found.append(int(p.name))
   except (ProcessLookupError,PermissionError):pass
 return found
def rss(pids):
 total=0
 for pid in pids:
  try:
   for line in pathlib.Path(f'/proc/{pid}/status').read_text().splitlines():
    if line.startswith('VmRSS:'):total+=int(line.split()[1])*1024;break
  except (OSError,ValueError):pass
 return total
record={'status':'started','started_at':utc(),'stage':'bundle','calls':{'Task_compile_attempts_reserved':0,'Task_compile_confirmed_completed':0,'Fraction_response_attempts':0,'Fraction_response_completed':0,'solver_process':0,'E0':0,'E1':0,'E2':0,'retry':0}}
BASE.mkdir(exist_ok=False);EVID.mkdir()
proc=None
try:
 assert sha(BUNDLE.read_bytes())==BUNDLE_SHA,'wrong bundle bytes'
 with tarfile.open(BUNDLE,'r:gz') as tf:
  members=tf.getmembers(); names=[m.name for m in members]
  assert len(names)==len(set(names))
  for m in members:
   q=pathlib.PurePosixPath(m.name);assert m.isfile() and not q.is_absolute() and '..' not in q.parts and q.parts,m.name
  manifest_bytes=tf.extractfile('bundle-manifest.json').read()
  assert sha(manifest_bytes)==MANIFEST_SHA,'wrong manifest bytes'
  manifest=json.loads(manifest_bytes); rows=manifest['files']
  assert len(rows)==len(members)-1 and {r['path'] for r in rows}==set(names)-{'bundle-manifest.json'}
  assert manifest['source_commit']=='4fc5e5e91e4a2ac9feaf05267c1f8ab713ca5990'
  WS.mkdir()
  for r in rows:
   q=pathlib.PurePosixPath(r['path']);assert q.parts and not q.is_absolute() and '..' not in q.parts
   data=tf.extractfile(r['path']).read();assert len(data)==r['bytes'] and sha(data)==r['sha256'],r['path']
   dest=WS.joinpath(*q.parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
  (WS/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 record.update(bundle_sha256=sha(BUNDLE.read_bytes()),source_files=len(rows),stage='dependencies')
 uv=cmd(['python3','-m','pip','show','uv'],5)
 if uv['returncode']:
  record['uv_bootstrap']=cmd(['python3','-m','pip','install','uv'],30)
  if record['uv_bootstrap']['returncode']:raise RuntimeError('uv bootstrap failed')
 import shutil
 uvbin=shutil.which('uv')
 if not uvbin:raise RuntimeError('uv executable unavailable')
 record['uv_sync']=cmd([uvbin,'sync','--locked','--python','3.12.13'],80,WS)
 if record['uv_sync']['returncode']:raise RuntimeError('locked uv sync failed')
 version=cmd([str(WS/'.venv/bin/python'),'--version'],5,WS)
 if version['returncode'] or (version['stdout']+version['stderr']).strip()!='Python 3.12.13':raise RuntimeError('Python 3.12.13 unavailable')
 record['stage']='probe';record['argv']=COMMAND
 env=os.environ.copy();env.update(PYTHONPATH='.:data/raw/a/official/code',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 def limits():
  resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 t=time.monotonic();highest=0;reason=None
 with (EVID/'probe.stdout').open('xb') as so,(EVID/'probe.stderr').open('xb') as se:
  record['calls'].update(Task_compile_attempts_reserved=None,Task_compile_confirmed_completed=None,Fraction_response_attempts=None,Fraction_response_completed=None,solver_process=None)
  record['unknown_call_upper_bounds']={'Task_compile':20,'Fraction_response':3}
  proc=subprocess.Popen(COMMAND,cwd=WS,env=env,start_new_session=True,preexec_fn=limits,stdout=so,stderr=se)
  record['calls']['solver_process']=1
  while proc.poll() is None:
   highest=max(highest,rss(owned(proc.pid)))
   if highest>512*1024*1024:reason='RSS>512MiB'
   if time.monotonic()-t>45:reason='process wall>45s'
   if reason:
    os.killpg(proc.pid,signal.SIGKILL);break
   time.sleep(.1)
  proc.wait(timeout=5)
  rem=owned(proc.pid)
  if rem:
   os.killpg(proc.pid,signal.SIGKILL);time.sleep(.2)
 record['probe']={'returncode':proc.returncode,'stop_reason':reason,'wall_seconds':time.monotonic()-t,'sampled_max_tree_rss_bytes':highest,'remaining_owned_pids':owned(proc.pid)}
 rp=TARGET/'report.json'
 if rp.exists():
  report=json.loads(rp.read_text());record['probe_report_status']=report.get('status')
  record['calls'].update(Task_compile_attempts_reserved=report.get('task_compile_attempts_reserved'),Task_compile_confirmed_completed=report.get('task_compile_confirmed_completed'),Fraction_response_attempts=report.get('response_attempts'),Fraction_response_completed=report.get('response_confirmed_completed'))
 plan=TARGET/'plan.json'
 plan_match=bool(rp.exists() and plan.exists() and report.get('plan_sha256')==sha(plan.read_bytes()))
 record['plan_sha256_verified']=plan_match
 record['status']='probe-complete' if proc.returncode==0 and not reason and rp.exists() and report.get('status')=='verified_model' and plan_match and not record['probe']['remaining_owned_pids'] else 'probe-failed'
except Exception as error:
 record.update(status='failed',error=f'{type(error).__name__}: {error}')
finally:
 if proc is not None:
  try:
   remaining=owned(proc.pid)
   if proc.poll() is None or remaining:
    os.killpg(proc.pid,signal.SIGKILL)
   proc.wait(timeout=5)
   record['process_group_cleanup_confirmed']=not owned(proc.pid)
  except (OSError,subprocess.TimeoutExpired) as cleanup_error:
   record['process_group_cleanup_confirmed']=False
   record['process_group_cleanup_error']=f'{type(cleanup_error).__name__}: {cleanup_error}'
  if not record['process_group_cleanup_confirmed']:
   record['status']='failed'
 record['finished_at']=utc();(EVID/'setup.json').write_text(json.dumps(record,indent=2)+'\n')
 files=[p for root in (EVID,TARGET) if root.exists() for p in root.rglob('*') if p.is_file()]
 rows=[{'path':p.relative_to(BASE).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(files)]
 (EVID/'evidence-manifest.json').write_text(json.dumps({'files':rows},indent=2)+'\n')
 with tarfile.open(BASE/'evidence.tar.gz','w:gz') as tf:
  for p in sorted(files+[EVID/'evidence-manifest.json']):tf.add(p,arcname=p.relative_to(BASE).as_posix(),recursive=False)
 print(json.dumps({'status':record['status'],'archive_sha256':sha((BASE/'evidence.tar.gz').read_bytes()),'files':len(rows)}))
