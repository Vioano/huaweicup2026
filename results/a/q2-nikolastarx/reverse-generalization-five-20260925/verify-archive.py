from pathlib import Path
import json,zipfile,hashlib,gzip,subprocess,datetime
p=Path(__file__).resolve().parent; root=next(q for q in p.parents if (q/"AGENTS.md").is_file() and (q/"src").is_dir());z=zipfile.ZipFile(p/'results.zip');cap=zipfile.ZipFile(p/'reverse-generalization-capsule.zip');h=lambda b:hashlib.sha256(b).hexdigest()
assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==65
assert all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist())
L=json.loads(z.read('pilot/ledger.json'));F=json.loads(z.read('pilot/freeze.json'))
assert h(z.read('pilot/freeze.json'))==L['freeze_sha256']==h((p/'freeze.json').read_bytes())
assert L['source_commit']=='675fdcb4f6527336f35ca3ec870bf59544485324' and L['status']=='completed' and L['in_flight'] is None
assert L['calls']=={'constructor':5,'E0':5,'E1':0,'E2':0,'retry':0}
rows=[]
for r,f in zip(L['rows'],F['cells']):
 c=r['case'];pre=f'pilot/{c}/';plan=z.read(pre+'plan.json');resraw=z.read(pre+'result.json');result=json.loads(resraw);solver=json.loads(z.read(pre+'constructor/solver.json'))
 assert h(plan)==r['plan_sha256']==solver['plan_sha256'] and h(resraw)==r['result_sha256']
 assert set(json.loads(plan))=={'node_to_subgraph','core_schedules'} and len(json.loads(plan)['core_schedules'])==5
 assert result['num_cores']==5 and result['makespan']==r['makespan'] and result['data_movement_bytes']==r['movement']
 assert solver['status']=='ok' and solver['calls']=={'E0':0,'E1':0,'E2':0}
 assert h(cap.read(f'data/raw/a/official/data/case_{c}.json'))==r['graph_sha256'];assert h(cap.read('data/raw/a/official/data/config.txt'))==F['config_sha256']
 old=root/r['baseline_archive'];oldres=gzip.decompress((old/'result.json.gz').read_bytes());oldplan=gzip.decompress((old/'plan.json.gz').read_bytes())
 assert h(oldres)==r['baseline_result_sha256'] and h(oldplan)==r['baseline_plan_sha256'];assert json.loads(oldres)['makespan']==r['baseline_M']
 for typ in ['constructor','E0']:
  proc=json.loads(z.read(pre+typ+'-process/process.json'));assert proc['status']=='ok' and proc['exit_code']==0 and not proc['surviving_pids'];assert any(str(a).endswith('case_'+c+'.json') for a in proc['argv'])
 rows.append({'case':c,'old_M':r['baseline_M'],'new_M':r['makespan'],'M_reduction_pct':100*(r['baseline_M']-r['makespan'])/r['baseline_M'],'old_added_DDR':r['baseline_added_DDR'],'new_added_DDR':r['movement']['added_copy_bytes']})
b=json.loads(z.read('bootstrap.json'));assert b['exit_code']==0 and not b['final_surviving_pids'] and b['observer_inclusive_peak_rss_bytes']<536870912
out={'scope':'offline archived-result hash/metric/exit checks only','calls':L['calls'],'rows':rows,'runtime':b['runtime']};print(json.dumps(out,indent=2))
