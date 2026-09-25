"""Read preserved receipts across windows; no new solver/evaluator calls."""
import argparse,hashlib,json,statistics
from pathlib import Path
P=Path(__file__).absolute().parent; R=P.parents[1]
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
J=lambda p:json.loads(p.read_bytes())
a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);args=a.parse_args()
first=R/'output/bidirectional-holdout12-runtimefix-run-20260925';tail=R/'output/holdout-tail3-run-20260925'
s=J(first/'results/summary.json');t=J(tail/'summary.json');outer=J(first/'supervisor-receipt.json')
assert s['status']=='stopped_first_failure' and s['accepted_cells']==8 and s['call_count_complete']
assert not outer['surviving_pids'] and outer['exit_code']==1
assert t['status']=='completed' and t['call_count_complete'] and t['in_flight'] is None and len(t['rows'])==3
assert t['calls']['new_solver_started']==3 and t['calls']['E0_independent_started']==3 and t['calls']['E0_fallback_possible']==0
prep=R/'output/holdout-structural-route-fix-20260925'; manifest=J(prep/'local-holdout-manifest.json')
selection=J(prep/'selection-manifest.json');old={x['case']:x for x in J(prep/'c665-paired-baseline.json')['records']}
den={x['case']:x['makespan'] for x in J(prep/'singlecore-baseline.json')['records']}
entries=[(r,first/'results'/f"{r['case']}-k5",None) for r in s['rows'] if r['status']=='accepted']
recovered=J(R/'results/a/q2-nikolastarx/holdout-tail4-recovered097-20260925/readback.json')
assert recovered['calls_this_window']=={'new_solver':0,'E2':0,'independent_E0':1,'fallback':0,'retry':0}
recovered_root=Path('/Users/nikolastar/.codex/worktrees/p2-bidirectional-full500-s7d28/huaweicup2026/output/holdout-tail4-run-20260925/097-k5')
result097=J(recovered_root/'result.json')
r097={'case':'097','status':'accepted','new_solver_started':False,'old_solver_wall_seconds':recovered['solver_wall_seconds_from_previous_window'],'plan_sha256':recovered['plan_sha256'],'result_sha256':recovered['result_sha256'],'official':{'makespan':result097['makespan'],'data_movement_bytes':result097['data_movement_bytes']}}
entries += [(r097,recovered_root,first/'results/097-k5')]
entries += [(r,tail/f"{r['case']}-k5",None) for r in t['rows']]
assert [r['case'] for r,_,_ in entries]==[x[0] for x in selection['coordinates']]
rows=[]
for row,folder,reused in entries:
 c=row['case'];source=reused or folder;l=J(source/'online/solver.json');plan=source/'plan.json';result=J(folder/'result.json')
 assert row['status']=='accepted' and H(plan)==row['plan_sha256']==l['plan_sha256']
 assert H(folder/'result.json')==row['result_sha256']
 if 'solver_ledger_sha256' in row:assert H(source/'online/solver.json')==row['solver_ledger_sha256']
 assert l['status']=='ok' and l['solver_checkout_commit']==manifest['solver_source_commit']
 assert l['graph_sha256']==old[c]['graph_sha256'] and l['config_sha256']==old[c]['config_sha256'] and l['cores']==5
 assert l['calls']['E0_fallback']==0 and l['calls']['E0']==0 and not l['request_in_flight'] and l['possible_E0_fallback_calls']==0
 assert l['calls']['E2_api_attempted']==l['calls']['native_returns']==len(l['attempts'])<=4
 for attempt in l['attempts']:
  assert attempt['status']=='native' and H(source/'online'/attempt['plan_file'])==attempt['plan_sha256']
 sp=J(source/'solver-process/process.json');ep=J((R/'output/holdout-tail4-run-20260925/097-k5' if reused else folder)/'e0-process/process.json')
 for p in (sp,ep):assert p['status']=='ok' and p['exit_code']==0 and not p['surviving_pids']
 assert result['scene']=='B' and result['num_cores']==5
 assert result['makespan']==row['official']['makespan'] and result['data_movement_bytes']==row['official']['data_movement_bytes']
 if reused:assert row['new_solver_started'] is False and row['old_solver_wall_seconds']==sp['wall_seconds']
 current=result['makespan'];prior=old[c]['makespan'];d=l['detail']
 rows.append({'case':c,'cores':5,'old_M':prior,'new_M':current,'old_speedup':den[c]/prior,'new_speedup':den[c]/current,'speedup_delta':den[c]/current-den[c]/prior,'old_extra_DDR':old[c]['movement']['added_copy_bytes'],'new_extra_DDR':result['data_movement_bytes']['added_copy_bytes'],'solver_wall_seconds':sp['wall_seconds'],'solver_measurement_reused_from_prior_window':bool(reused),'E0_wall_seconds':ep['wall_seconds'],'E2_calls':l['calls']['E2_api_attempted'],'selected':d['selected'],'scores':d['scores'],'skip_reason':d['skip_reason'],'plan_sha256':H(plan),'result_sha256':H(folder/'result.json'),'solver_ledger_sha256':H(source/'online/solver.json'),'source_window':source.relative_to(R).as_posix(),'official_window':str(folder) if reused else folder.relative_to(R).as_posix()})
out={'scope':'All preregistered12 K5 case evidence for the same15d solver, collected across separately recorded windows; not full100/full500 or a failure-free batch','solver_commit':manifest['solver_source_commit'],'selection_sha256':H(prep/'selection-manifest.json'),'old_mean_speedup':statistics.mean(r['old_speedup'] for r in rows),'new_mean_speedup':statistics.mean(r['new_speedup'] for r in rows),'win_tie_loss':[sum(r['new_M']<r['old_M'] for r in rows),sum(r['new_M']==r['old_M'] for r in rows),sum(r['new_M']>r['old_M'] for r in rows)],'extra_DDR_old_sum':sum(r['old_extra_DDR'] for r in rows),'extra_DDR_new_sum':sum(r['new_extra_DDR'] for r in rows),'accepted_algorithm_cells':12,'E2_native_returns_for_these_cells':sum(r['E2_calls'] for r in rows),'independent_E0_for_these_cells':12,'prior_import_failure_accounting':{'solver':1,'E2_attempt':1,'possible_E0_fallback_reserve':1},'prior_tail4_producer_status':'stopped after successful097E0, original count-incomplete retained separately','new_readback_calls':0,'rows':rows,'timing_scope':'Each cold solver wall retained from its actual source window.097 has no new solver in tail window. Shared-host timings are not an isolated speed experiment.'}
with args.output.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
