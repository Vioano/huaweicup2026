import hashlib,json,os,pathlib,platform,resource,signal,subprocess,sys,tarfile,time,shutil
BASE=pathlib.Path('/content/p1_resource_cut_window'); BUNDLE=pathlib.Path('/content/p1-resource-cut-source-bundle.tar.gz')
WS=BASE/'workspace'; EVID=BASE/'evidence'; OUT=WS/'results/a/p1-resource-cut-colab-20260925/run-20260925T-window'
BASE.mkdir(exist_ok=True); EVID.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,timeout,cwd=None):
 t=time.monotonic(); p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
 return {'argv':cmd,'returncode':p.returncode,'wall_seconds':time.monotonic()-t,'stdout':p.stdout,'stderr':p.stderr}
setup={'status':'started','started_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stage':'bundle-verify','calls':{'Task_compile_attempts_reserved':0,'Task_compile_confirmed_completed':0,'Fraction_response_attempts':0,'Fraction_response_completed':0,'solver':0,'E0':0,'E1':0,'E2':0,'retry':0}}
try:
 assert BUNDLE.is_file(); setup['bundle_sha256']=sha(BUNDLE); setup['bundle_bytes']=BUNDLE.stat().st_size
 WS.mkdir(exist_ok=False)
 with tarfile.open(BUNDLE,'r:gz') as tf:
  members=tf.getmembers(); names=[m.name for m in members]; assert len(names)==len(set(names))
  for m in members:
   q=pathlib.PurePosixPath(m.name); assert not q.is_absolute() and '..' not in q.parts and m.isfile(),m.name
  manifest=json.load(tf.extractfile('bundle-manifest.json'))
  for r in manifest['files']:
   p=pathlib.PurePosixPath(r['path']); data=tf.extractfile(r['path']).read(); assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
   dest=WS.joinpath(*p.parts); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
 (WS/'bundle-manifest.json').write_bytes(tf.extractfile('bundle-manifest.json').read())
 setup['source_manifest_files']=len(manifest['files']); setup['stage']='python-uv-sync'
 py=subprocess.run(['python3','--version'],capture_output=True,text=True,timeout=5); setup['bootstrap_python']=py.stdout.strip() or py.stderr.strip()
 uvpath=shutil.which('uv')
 if not uvpath:
  setup['uv_bootstrap']=run(['python3','-m','pip','install','uv'],30)
  uvpath=shutil.which('uv')
 if not uvpath: raise RuntimeError('uv unavailable after bounded bootstrap')
 if uv.returncode: raise RuntimeError('uv unavailable after bounded bootstrap')
 setup['uv_path']=uvpath; sync=run([setup['uv_path'],'sync','--locked','--python','3.12.13'],80,cwd=WS); setup['uv_sync']=sync
 if sync['returncode']: raise RuntimeError('uv sync --locked failed')
 pybin=WS/'.venv/bin/python'; v=run([str(pybin),'--version'],5,cwd=WS); setup['selected_python']=v['stdout'].strip()
 if setup['selected_python']!='Python 3.12.13': raise RuntimeError('required Python 3.12.13 unavailable')
 setup['stage']='probe'; setup['probe_started']=True; setup['budget_limits']={'Task_compiles_max':20,'Fraction_responses_max':2,'solver':0,'E0':0,'E1':0,'E2':0,'retry':0}; OUT.parent.mkdir(parents=True,exist_ok=True)
 stdout=EVID/'probe.stdout.txt'; stderr=EVID/'probe.stderr.txt'; started=time.monotonic(); proc=None; setup['probe_started']=True; setup['calls'].update(Task_compile_attempts_reserved=None, Task_compile_confirmed_completed=None, Fraction_response_attempts=None, Fraction_response_completed=None); setup['unobserved_call_upper_bounds']={'Task_compile':20,'Fraction_response':2}
 def limits():
  resource.setrlimit(resource.RLIMIT_CPU,(30,30)); resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024)); resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 with stdout.open('xb') as so,stderr.open('xb') as se:
  proc=subprocess.Popen([str(pybin),'-B','src/review/p1_resource_cut_probe.py','--execute','--output',str(OUT)],cwd=WS,start_new_session=True,preexec_fn=limits,stdout=so,stderr=se)
  try: rc=proc.wait(timeout=30); state='exited'
  except subprocess.TimeoutExpired:
   state='timeout'; os.killpg(proc.pid,signal.SIGKILL); proc.wait(timeout=3)
  setup['probe_process']={'pid':proc.pid,'state':state,'returncode':proc.returncode,'wall_seconds':time.monotonic()-started,'timeout_seconds':30,'address_space_limit_bytes':512*1024*1024,'cleanup_confirmed':proc.poll() is not None}
 report=OUT/'report.json'
 if report.exists():
  rep=json.loads(report.read_text()); setup['probe_status']=rep.get('status'); setup['calls']=rep.get('calls',setup['calls'])
 else:
  setup['calls']={'Task_compile_attempts_reserved':None,'Task_compile_confirmed_completed':None,'Fraction_response_attempts':None,'Fraction_response_completed':None,'solver':0,'E0':0,'E1':0,'E2':0,'retry':0}; setup['call_counts_unknown_due_to_missing_report']=True
 setup['status']='complete' if setup.get('probe_status')=='success' and setup['probe_process']['returncode']==0 else 'probe_failed'
except Exception as e:
 setup.update(status='failed',error=f'{type(e).__name__}: {e}')
finally:
 setup['finished_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); (EVID/'setup.json').write_text(json.dumps(setup,indent=2)+'\n')
 files=[p for root in [WS/'results/a/p1-resource-cut-colab-20260925',EVID] if root.exists() for p in root.rglob('*') if p.is_file()]
 if (WS/'bundle-manifest.json').exists(): files.append(WS/'bundle-manifest.json')
 rows=[]
 for p in sorted(set(files)):
  rows.append({'path':p.relative_to(BASE).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
 mp=EVID/'evidence-manifest.json'; mp.write_text(json.dumps({'files':rows},indent=2)+'\n')
 with tarfile.open(BASE/'evidence.tar.gz','w:gz') as tf:
  for p in sorted(set(files+[mp])):tf.add(p,arcname=p.relative_to(BASE).as_posix(),recursive=False)
 print(json.dumps({'status':setup['status'],'stage':setup.get('stage'),'probe_status':setup.get('probe_status'),'calls':setup['calls'],'files':len(rows),'archive_bytes':(BASE/'evidence.tar.gz').stat().st_size,'archive_sha256':sha(BASE/'evidence.tar.gz')}))
