"""Validate package, locked deps and run only the two frozen solver/E0 cells."""
import ctypes,hashlib,json,os,pathlib,resource,signal,subprocess,tarfile,time
BASE=pathlib.Path('/content/p1_structural_two_cell');BUNDLE=pathlib.Path('/content/two-cell-source-bundle.tar.gz');WS=BASE/'workspace';EVID=BASE/'evidence';OUT=WS/'two-cell-run';BUNDLE_SHA='92327688f92c5878dff2803a3121e8e46bec4f077d0d6ba690e9c43de6df6972';MAX_REMOTE=540

def sha(b):return hashlib.sha256(b).hexdigest()
def proc_start(pid):
 try:return int(pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[19])
 except (OSError,ValueError,IndexError):return None
def kill_ident(r):
 p=r.get('pid');g=r.get('pgid');s=r.get('linux_proc_start_ticks')
 if type(p)is not int or type(g)is not int or type(s)is not int or p<=1 or p!=g:return {'confirmed':False,'reason':'identity missing'}
 try:
  if proc_start(p)!=s:return {'confirmed':proc_start(p) is None,'exited':True}
  if os.getpgid(p)!=g:return {'confirmed':False,'reason':'pgid changed'}
  os.killpg(g,signal.SIGKILL)
 except ProcessLookupError:return {'confirmed':True,'exit_race':True}
 except PermissionError:return {'confirmed':False,'reason':'permission'}
 end=time.monotonic()+6
 while time.monotonic()<end and proc_start(p)==s:time.sleep(.05)
 return {'confirmed':proc_start(p)!=s,'exited':proc_start(p)!=s}
def adopted():
 found={}
 for d in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   pid=int(d.name);stat=(d/'stat').read_text().rsplit(') ',1)[1].split();ppid=int(stat[1]);start=int(stat[19]);cwd=os.readlink(d/'cwd')
   if ppid==os.getpid() and (cwd==str(WS) or cwd.startswith(str(WS)+'/')):found[pid]=start
  except (OSError,ValueError,IndexError):pass
 return found
def reap_adopted():
 seen=adopted()
 for _ in range(20):
  for pid,start in seen.items():
   if proc_start(pid)==start:
    try:os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:pass
    try:os.waitpid(pid,os.WNOHANG)
    except (ChildProcessError,ProcessLookupError):pass
  time.sleep(.1);live=[p for p,s in seen.items() if proc_start(p)==s]
  if not live:return {'confirmed':True,'observed':sorted(seen),'remaining':[]}
  seen.update(adopted())
 return {'confirmed':False,'observed':sorted(seen),'remaining':[p for p,s in seen.items() if proc_start(p)==s]}
def cleanup_runner(child,identity):
 if child is None:return {'confirmed':True,'launched':False}
 result={'confirmed':False,'pid':child.pid}
 try:
  if child.poll() is None:
   group_matches=False
   try:
    group_matches=bool(identity and identity.get('pid')==child.pid and identity.get('pgid')==child.pid and type(identity.get('linux_proc_start_ticks')) is int and proc_start(child.pid)==identity['linux_proc_start_ticks'] and os.getpgid(child.pid)==child.pid)
   except Exception as e:result['identity_error']=f'{type(e).__name__}: {e}'
   if group_matches:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    except Exception as e:
     result['group_kill_error']=f'{type(e).__name__}: {e}';child.kill()
   else:child.kill()
 except ProcessLookupError:pass
 except Exception as e:result['kill_error']=f'{type(e).__name__}: {e}'
 try:
  result['exit_code']=child.wait(timeout=8);result['confirmed']=True
 except Exception as e:result['wait_error']=f'{type(e).__name__}: {e}'
 return result
def main():
 BASE.mkdir(exist_ok=False);EVID.mkdir();start=time.monotonic();rec={'status':'started','calls':{'solver':0,'E1':None,'E0':0,'E2':0,'retry':0},'E1_reserved_max':18};child=None;runner_identity=None
 try:
  if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)!=0:raise OSError('cannot arm subreaper')
  raw=BUNDLE.read_bytes();assert sha(raw)==BUNDLE_SHA
  with tarfile.open(BUNDLE,'r:gz') as tf:
   members=tf.getmembers();names=[m.name for m in members];assert len(names)==len(set(names)) and all(m.isfile() and not pathlib.PurePosixPath(m.name).is_absolute() and '..' not in pathlib.PurePosixPath(m.name).parts for m in members)
   bm=json.loads(tf.extractfile('bundle-manifest.json').read());assert set(names)=={x['path'] for x in bm['files']}|{'bundle-manifest.json'};WS.mkdir()
   for row in bm['files']:
    b=tf.extractfile(row['path']).read();assert len(b)==row['bytes'] and sha(b)==row['sha256'];dst=WS/row['path'];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
  assert bm['solver_commit']=='3a1b82b71ca1ff6689eb8e72f17d26c48b52073c'
  uv=subprocess.run(['python3','-m','pip','show','uv'],capture_output=True,text=True,timeout=8)
  if uv.returncode:subprocess.run(['python3','-m','pip','install','uv'],capture_output=True,text=True,timeout=35,check=True)
  u=subprocess.run(['uv','sync','--locked','--python','3.12.13'],cwd=WS,capture_output=True,text=True,timeout=100,check=True);rec['uv_sync_stdout']=u.stdout[-1000:]
  deadline=start+MAX_REMOTE-30;assert deadline-time.monotonic()>300,'insufficient time for one solver/E0 pair'
  argv=['.venv/bin/python','-B','-m','src.review.p1_structural_two_cell_once','--output-root',str(OUT),'--deadline-monotonic',str(deadline)]
  # runner receives a same-host monotonic deadline and enforces per-stage caps
  rec['argv']=argv;rec['stage']='two-cell-runner';(EVID/'runner.stdout.txt').touch(exist_ok=False);(EVID/'runner.stderr.txt').touch(exist_ok=False)
  with (EVID/'runner.stdout.txt').open('wb') as so,(EVID/'runner.stderr.txt').open('wb') as se:
   child=subprocess.Popen(argv,cwd=WS,stdout=so,stderr=se,start_new_session=True,env={**os.environ,'PYTHONPATH':'.:data/raw/a/official/code','PYTHONDONTWRITEBYTECODE':'1'});runner_identity={'pid':child.pid,'pgid':os.getpgid(child.pid),'linux_proc_start_ticks':proc_start(child.pid)};(EVID/'runner-live.json').write_text(json.dumps(runner_identity)+'\n')
   try:rc=child.wait(timeout=max(1,deadline-time.monotonic()))
   except subprocess.TimeoutExpired:
    live=list(OUT.glob('*/process-live.json'))
    rec['child_cleanup']=kill_ident(json.loads(live[-1].read_text())) if live else {'confirmed':False,'reason':'no identity'}
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    rc=child.wait(timeout=8);rec['outer_timeout']=True
  attempt=json.loads((OUT/'attempt.json').read_text()) if (OUT/'attempt.json').exists() else {};rec['attempt']=attempt;rec['calls']=attempt.get('calls',rec['calls']);rec['runner_exit']=rc
  rec['status']='complete' if rc==0 and attempt.get('status')=='complete' and attempt.get('worker_cleanup',{}).get('confirmed') else 'failed'
 except Exception as e:rec.update(status='failed',error=f'{type(e).__name__}: {e}')
 finally:
  live=list(OUT.glob('*/process-live.json')) if OUT.exists() else []
  if live:
   try:rec['stage_child_cleanup']=kill_ident(json.loads(live[-1].read_text()))
   except Exception as e:rec['stage_child_cleanup']={'confirmed':False,'error':str(e)}
  rec['runner_cleanup']=cleanup_runner(child,runner_identity)
  rec['runner_exited']=rec['runner_cleanup']['confirmed']
  if not rec['runner_exited']:rec['runner_residual']=True
  try:rec['adopted_cleanup']=reap_adopted()
  except Exception as e:rec['adopted_cleanup']={'confirmed':False,'error':str(e)}
  if rec.get('status')=='complete' and (not rec.get('adopted_cleanup',{}).get('confirmed') or rec.get('runner_residual') or rec.get('stage_child_cleanup',{}).get('confirmed') is False):rec['status']='cleanup-unconfirmed'
  rec['remote_wall_seconds']=time.monotonic()-start;rec['peak_child_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
  (EVID/'setup.json').write_text(json.dumps(rec,indent=2)+'\n');files=[p for p in (EVID,OUT) if p.exists() for p in p.rglob('*') if p.is_file()];rows=[{'path':x.relative_to(BASE).as_posix(),'bytes':x.stat().st_size,'sha256':sha(x.read_bytes())} for x in sorted(files)];(EVID/'evidence-manifest.json').write_text(json.dumps({'files':rows},indent=2)+'\n')
  with tarfile.open(BASE/'evidence.tar.gz','w:gz') as t:
   for f in sorted(files+[EVID/'evidence-manifest.json']):t.add(f,arcname=f.relative_to(BASE).as_posix(),recursive=False)
 print(json.dumps({'status':rec['status'],'archive_sha256':sha((BASE/'evidence.tar.gz').read_bytes())}))
if __name__=='__main__':main()
