from pathlib import Path
import datetime,hashlib,json,os,platform,subprocess,sys,time
root=Path(__file__).resolve().parents[1];ledger=[]
for name in ['whole_seed','period7_seed']:
 cmd=[sys.executable,'-B',str(root/'src/replay_once.py'),name,'--root',str(root),'--out',str(root/f'results/{name}.json')]
 receipt={'variant':name,'argv':cmd,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'timeout_seconds':30,'worker_count':1,'retries':0}
 t=time.perf_counter()
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  receipt.update(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
 except subprocess.TimeoutExpired as e:
  receipt.update(returncode=None,status='timeout',stdout=str(e.stdout),stderr=str(e.stderr))
 receipt['wall_seconds']=time.perf_counter()-t
 ledger.append(receipt)
 (root/'results/ledger.json').write_text(json.dumps({'environment':{'python':sys.version,'platform':platform.platform()},'runs':ledger},indent=2))
 print(receipt)
 if receipt['returncode']!=0:
  raise SystemExit('STOP; no second attempt or other plan evaluation permitted')
