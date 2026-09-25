"""Read-only pairing after the independent holdout selection was frozen."""
import gzip,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
R=next(q for q in P.parents if (q/'scripts/q2_bidirectional_holdout.py').is_file() and (q/'pyproject.toml').is_file())
SRC='c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
s=read(P/'selection-manifest.json'); assert sha((P/'selection-manifest.json').read_bytes())=='6060d2a281e963614eb0634dbf90454b3b7b52be73d0d6cc67287436e33d16b1'
old_manifest_path=R/'results/a/q2-nikolastarx/hypergap-full500-20260925/manifest-workers2.json'
om=read(old_manifest_path);assert om['solver_commit']==SRC
archive=R/'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
summary_path=R/'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
su=read(summary_path);assert su['solver_commit']==SRC and su['status']=='completed'
rows=[]
selected={x['case']:x for q in s['strata'] for x in q['members']}
for c,k in s['coordinates']:
 lo=((int(c)-1)//10)*10+1; d=archive/f'cases-{lo:03d}-{lo+9:03d}'/f'{c}-k{k}'
 run=read(d/'run.json'); cell=read(d/'cell.json'); ledger=read(d/'online-ledger.json'); proc=read(d/'solver-process.json'); e0proc=read(d/'e0-process.json')
 for item in run['archived_evidence'].values(): assert sha((R/item['path']).read_bytes())==item['sha256']
 assert ledger['solver_checkout_commit']==su['runner_commit']
 for n,h in om['solver_sources'].items(): assert ledger['solver_source_sha256'][Path(n).name]==h,n
 assert cell['case']==c and cell['cores']==k and cell['status']=='accepted'
 assert cell['graph_sha256']==selected[c]['graph_sha256']==ledger['graph_sha256']
 assert cell['config_sha256']==ledger['config_sha256']
 assert proc['status']=='ok' and proc['exit_code']==0 and not proc['surviving_pids']
 assert e0proc['status']=='ok' and e0proc['exit_code']==0 and not e0proc['surviving_pids']
 assert ledger['status']=='ok' and not ledger['request_in_flight'] and ledger['calls']['E0_fallback']==0
 pr=gzip.decompress((d/'plan.json.gz').read_bytes());rr=gzip.decompress((d/'result.json.gz').read_bytes()); res=json.loads(rr)
 assert sha(pr)==cell['plan_sha256']==ledger['plan_sha256']
 assert sha(rr)==cell['official']['result_sha256']
 assert res['makespan']==cell['official']['makespan'] and res['data_movement_bytes']==cell['official']['movement']
 assert proc['wall_seconds']==cell['solver_process']['wall_seconds']
 assert cell['calls']['E2_api_attempted']==ledger['calls']['E2_api_attempted']
 rows.append({'case':c,'cores':k,'node_count':selected[c]['node_count'],'graph_sha256':cell['graph_sha256'],'config_sha256':cell['config_sha256'],'makespan':res['makespan'],'movement':res['data_movement_bytes'],'cross_task_traffic':res['cross_task_traffic'],'solver_wall_seconds':proc['wall_seconds'],'external_E0_wall_seconds':e0proc['wall_seconds'],'calls':ledger['calls'],'original_plan_sha256':sha(pr),'original_result_sha256':sha(rr),'recorded_checkout':ledger['solver_checkout_commit'],'archive_folder':d.relative_to(R).as_posix(),'artifacts':{f.name:{'path':f.relative_to(R).as_posix(),'sha256':sha(f.read_bytes())} for f in d.iterdir() if f.is_file()}})
out={'schema':'p2-holdout12-c665-pair-v1','source_solver_commit':SRC,'historical_runner_commit':su['runner_commit'],'selection_sha256':sha((P/'selection-manifest.json').read_bytes()),'old_manifest':{'path':old_manifest_path.relative_to(R).as_posix(),'sha256':sha(old_manifest_path.read_bytes())},'old_summary':{'path':summary_path.relative_to(R).as_posix(),'sha256':sha(summary_path.read_bytes())},'notes':'Historical complete-solver wall from the previous shared-host run; paired provenance, not new-version timing or controlled isolated speed comparison. No solver or evaluator invoked. Selection frozen before this read. Stored sanitized hashes and original JSON hashes checked separately.','records':rows,'new_score_calls':0}
with (P/'c665-paired-baseline.json').open('x') as f: json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'pairs':len(rows),'baseline':[(r['case'],r['makespan'],round(r['solver_wall_seconds'],3)) for r in rows]}))
