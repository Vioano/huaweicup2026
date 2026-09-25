"""Remote single-run R5 phase pair; records diagnostics even after runner failure."""
import gzip,hashlib,json,os,pathlib,resource,shutil,signal,subprocess,sys,tarfile,time
BASE=pathlib.Path('/content/p1_r5_phase_window');BUNDLE=pathlib.Path('/content/r5-source-bundle.tar.gz')
WS=BASE/'workspace';EVID=BASE/'evidence';TARGET=WS/'evidence/r5-008-k5'
BUNDLE_SHA='0c5ca3078bc60f5eb6f40567be41047dfe9c655e405400bc49a9c016edd7edd8'
SOURCE='8e63305f86a3692b9552295c61c4f234a006c105';GRAPH='c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d'
COMMAND=['.venv/bin/python','-B','-m','src.review.p1_real_work_phase_probe','case_008.json','--cores','5','--capacity-l1','524288','--capacity-ub','131072','--bandwidth','60','--gate','100','--q','7','--s','3','--period','35405','--chain-work','4512','--threshold','99264','--expect-graph-sha256',GRAPH,'--output-root','evidence/r5-008-k5','--execute']
def sha(b):return hashlib.sha256(b).hexdigest()
def cmd(argv,timeout,cwd=None):
 t=time.monotonic();p=subprocess.run(argv,cwd=cwd,text=True,capture_output=True,timeout=timeout)
 return {'argv':argv,'returncode':p.returncode,'wall_seconds':time.monotonic()-t,'stdout':p.stdout[-4000:],'stderr':p.stderr[-4000:]}
def owned(pgid):
 out=[]
 for q in pathlib.Path('/proc').iterdir():
  if q.name.isdecimal():
   try:
    if os.getpgid(int(q.name))==pgid:out.append(int(q.name))
   except (ProcessLookupError,PermissionError):pass
 return out
record={'status':'started','started_at':time.time(),'calls':{'Task_compile_attempts_upper_bound':53,'Task_compile_confirmed':None,'Fraction_attempts_upper_bound':2,'Fraction_confirmed':None,'E0':0,'E1':0,'E2':0,'retry':0}}
proc=None
BASE.mkdir(parents=True,exist_ok=False);EVID.mkdir()
try:
 assert sha(BUNDLE.read_bytes())==BUNDLE_SHA,'bundle SHA mismatch'
 with tarfile.open(BUNDLE,'r:gz') as tf:
  ms=tf.getmembers();names=[m.name for m in ms]
  assert len(names)==len(set(names))
  for m in ms:
   q=pathlib.PurePosixPath(m.name);assert m.isfile() and q.parts and not q.is_absolute() and '..' not in q.parts
  raw=tf.extractfile('bundle-manifest.json').read();manifest=json.loads(raw)
  assert manifest['source_commit']==SOURCE and manifest['graph_sha256']==GRAPH
  rows=manifest['files'];assert set(names)=={r['path'] for r in rows}|{'bundle-manifest.json'}
  WS.mkdir(parents=True,exist_ok=False)
  for r in rows:
   data=tf.extractfile(r['path']).read();assert len(data)==r['bytes'] and sha(data)==r['sha256'],r['path']
   dest=WS/r['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
  (WS/'bundle-manifest.json').write_bytes(raw)
 assert sha((WS/'case_008.json').read_bytes())==GRAPH
 record['source_files']=len(rows);record['bundle_sha256']=BUNDLE_SHA
 uv=cmd(['python3','-m','pip','show','uv'],5)
 if uv['returncode']:record['uv_bootstrap']=cmd(['python3','-m','pip','install','uv'],35)
 uvbin=shutil.which('uv')
 if not uvbin:raise RuntimeError('uv unavailable')
 record['uv_sync']=cmd([uvbin,'sync','--locked','--python','3.12.13'],100,WS)
 if record['uv_sync']['returncode']:raise RuntimeError('uv sync failed')
 env=os.environ.copy();env.update(PYTHONPATH='.:data/raw/a/official/code',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 record['command']=COMMAND;record['stage']='runner';TARGET.parent.mkdir(parents=True,exist_ok=True)
 with (EVID/'runner.stdout').open('xb') as so,(EVID/'runner.stderr').open('xb') as se:
  proc=subprocess.Popen(COMMAND,cwd=WS,env=env,start_new_session=True,stdout=so,stderr=se)
  try:rc=proc.wait(timeout=180)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGKILL);rc=proc.wait(timeout=8);record['runner_timeout']=True
  record['runner_returncode']=rc;record['remaining_runner_pids']=owned(proc.pid)
 if record['remaining_runner_pids']:
  os.killpg(proc.pid,signal.SIGKILL);record['remaining_runner_pids']=owned(proc.pid)
 rp=TARGET/'diagnostics.json'
 if rp.exists():
  d=json.loads(rp.read_text());calls=d.get('calls',{})
  record['diagnostics_status']=d.get('status');record['calls']['Task_compile_confirmed']=calls.get('Task_compile_confirmed')
  record['calls']['Fraction_confirmed']=calls.get('Fraction_attempts')
  record['diagnostics_sha256']=sha(rp.read_bytes())
 record['status']='phase-pair-complete-NOT-E0' if record.get('runner_returncode')==0 and record.get('diagnostics_status')=='model_pair_complete_NOT_E0' else 'runner-failed-diagnostics-preserved'
except Exception as e:record.update(status='setup-failed',error=f'{type(e).__name__}: {e}')
finally:
 if proc is not None and proc.poll() is None:
  os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=8)
 record['finished_at']=time.time();(EVID/'setup.json').write_text(json.dumps(record,indent=2)+'\n')
 files=[x for root in (EVID,TARGET) if root.exists() for x in root.rglob('*') if x.is_file()]
 rows=[{'path':x.relative_to(BASE).as_posix(),'bytes':x.stat().st_size,'sha256':sha(x.read_bytes())} for x in sorted(files)]
 (EVID/'evidence-manifest.json').write_text(json.dumps({'files':rows},indent=2)+'\n')
 with tarfile.open(BASE/'evidence.tar.gz','w:gz') as tf:
  for x in sorted(files+[EVID/'evidence-manifest.json']):tf.add(x,arcname=x.relative_to(BASE).as_posix(),recursive=False)
 print(json.dumps({'status':record['status'],'verified_diagnostics':bool((TARGET/'diagnostics.json').exists()),'archive_sha256':sha((BASE/'evidence.tar.gz').read_bytes())}))
