#!/usr/bin/env python3
"""Map retained 071/K5 integration originals into board-submission-v1; no scoring."""
import gzip, hashlib, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
D = ROOT / 'results/a/q3-nikolastarx/query-flow-integration-20260925'
PLAN = D / 'run/plan.json'
P3 = D / 'run/evidence/p3-query_flow/result.json.gz'
P2 = D / 'run/evidence/p2-query_flow/result.json.gz'
BASE = ROOT / 'results/benchmark-board/official-singlecore-20260924/071/result.json.gz'
CONTROL = D / 'integration-control/receipt.json'
OUTER = D / 'run/outer_receipt.json'
LEDGER = D / 'run/outer_e0_ledger.json'
SAMPLES = D / 'integration-control/samples.jsonl'
MANIFEST = D / 'integration-manifest.json'
FROZEN = 'c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43'
DELIVERY = 'c1edb49324fd8ff45cabecec02cf051ab5ddd119'
PLAN_SHA = 'b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136'
BASE_SHA = 'd2e46fd00db3766c4ca574084cde6d94b1aa062cab5b5199474c86013e51daa5'
GRAPH = '437cc74cae9e0fc0cb89b05403c62062ceff8d5bc2224c8834c519e69524e897'
CONFIG = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
OFFICIAL = 'de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
REPO = 'huaweibei123/huaweicup2026'
RUN_ID = 'q3-query-flow-unified-071-k5-20260925T132224Z'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rd = lambda p: json.loads(p.read_text())
gz = lambda p: json.loads(gzip.decompress(p.read_bytes()))
art = lambda p: {'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
code = lambda commit,path,entry: {'repo':REPO,'commit':commit,'path':path,'entrypoint':entry}
def main():
    c, o, ledger, m = rd(CONTROL), rd(OUTER), rd(LEDGER), rd(MANIFEST)
    p3, p2 = gz(P3), gz(P2)
    assert c['status']=='complete' and c['exit_code']==0 and o['status']=='complete'
    assert c['frozen_solver_commit']==FROZEN and c['delivery_head']==DELIVERY and o['e0_calls']==6
    assert len(ledger)==6 and all(x['status']=='complete' for x in ledger)
    assert m['source_commit']==FROZEN and sha(PLAN)==PLAN_SHA
    assert sha(BASE)==BASE_SHA and gz(BASE).get('scene')=='A' and gz(BASE).get('num_cores')==1 and gz(BASE).get('makespan')==18919
    assert p3['scene']=='B' and p3['problem']==3 and p3['num_cores']==5 and p3['makespan']==5785
    assert p2['scene']=='B' and p2['num_cores']==5 and p2['makespan']==7070
    assert len(ledger)==4+2 and ledger[3]['phase']=='p3' and ledger[5]['phase']=='p2'
    planref=art(PLAN); resultrefs={'P3':art(P3),'P2':art(P2)}
    base={'graph_sha256':GRAPH,'config_sha256':CONFIG,'official_sha256':OFFICIAL,'route':'E0','entrypoint':'singlecore_evaluate.evaluate_singlecore','result':art(BASE)}
    common={'graph_sha256':GRAPH,'config_sha256':CONFIG,'official_sha256':OFFICIAL,'plan_sha256':PLAN_SHA}
    start=c['T0'].replace('+00:00','Z'); finish=c['T1'].replace('+00:00','Z')
    outer_wall=c['outer_supervisor_wall_seconds']; evals=rd(D/'run/evidence/evaluations.json')
    # Ordinal 3 and 5 are the final P3 and P2 evaluations of the retained plan.
    eval_wall={'P3':evals[3]['seconds'],'P2':evals[5]['seconds']}
    notes=[
      'Single fresh unified solver construction/selection on official 071/K5; localized evidence only, not a full algorithm/full-500 result or generalization claim.',
      f'Unified run ID {RUN_ID}; frozen algorithm source {FROZEN}, delivery/runner source {DELIVERY}. They are intentionally reported separately.',
      f'Solver wall uses the complete measured supervisor lifecycle window {outer_wall}s, including pre-child sampling, monitoring, and post-child terminal checks/cleanup. Child T0/T1 are lifecycle markers inside this window; their difference is not solver_wall. The outer runner receipt ({OUTER.relative_to(ROOT).as_posix()}, SHA256 {sha(OUTER)}) is retained as a diagnostic reference. All six online E0 calls are included and must not be added again; OS cold cache was not established. Runner-entry wall was {o["outer_wall_seconds"]}s and is diagnostic only.',
      'One shared invocation produced both P3 and its same-plan P2 guard; the two feed rows are paired views, not two solver invocations. Total run accounting is 1 solver invocation and 6 E0 calls (4 P3, 2 P2), zero retries.',
      'Manifest retains resource_policy_proposal="proposal_pending_scheduler_approval" despite separate explicit admission and successful execution; original manifest/control evidence is preserved unchanged.',
      f'P3 cache hit rate is byte-based: {p3["cache_stats"]["hit_bytes"]} hit bytes / {p3["cache_stats"]["hit_bytes"]+p3["cache_stats"]["miss_bytes"]} total; scheduled movement is not a physical DDR counter.'
    ]
    missing={'provenance.environment.cpu':'Exact CPU model is not in retained execution receipt.', 'provenance.environment.ram_bytes':'RAM capacity is not in retained execution receipt.','provenance.environment.dependencies':'Dependency environment fingerprint is not in retained execution receipt.', 'provenance.environment.threads':'Thread count is not recorded.', 'provenance.environment.peak_rss_bytes':'One-second supervisor samples do not certify process peak RSS.', 'provenance.measurement.cold_start':'OS/filesystem cache state was not established.', 'provenance.measurement.seed':'No random seed; single deterministic selected construction.'}
    records=[]
    for problem,phase,res,ordinal,calls in [('P3','P3',p3,3,4),('P2','P2',p2,5,2)]:
      records.append({
       'attempt_id':f'nikolastarx-query-flow-unified-071-k5-{phase.lower()}','revision':1,'run_id':RUN_ID,
       'algorithm_id':'q3-query-flow-unified','algorithm_name':'Q3 unified query-flow solver','variant':'guarded-query-flow-selection-071-k5',
       'solver_commit':FROZEN,'parameters':{'cores':5,'selected_plan_sha256':PLAN_SHA,'candidate_evaluations':{'P3':4,'P2':2},'retries':0},
       'problem':problem,'case_id':'071','cores':5,'status':'ok',
       'metrics':{'makespan_cycles':res['makespan'],'solver_wall_seconds':outer_wall,'evaluation_wall_seconds':eval_wall[problem],
          'ddr_bytes':res['data_movement_bytes']['scheduled_copy_bytes'],'extra_ddr_bytes':res['data_movement_bytes']['added_copy_bytes'],
          'spill_bytes':res['data_movement_bytes']['spill_added_copy_bytes'],'cache_hit_rate':res.get('cache_stats',{}).get('hit_rate')},
       'evaluator':{'route':'E0','commit':FROZEN,'entrypoint':'multicore_cut_evaluate_problem_3.evaluate_problem_3' if problem=='P3' else 'multicore_cut_evaluate_problem_2.evaluate_scene_b'},
       'identity':common,'artifacts':{'plan':planref,'result':resultrefs[problem],'run':art(CONTROL),'trace':art(LEDGER),'log':art(SAMPLES),'manifest':art(MANIFEST)},
       'runtime_id':'macos-arm64-local-shared','observed_at':start,
       'timing':{'solver_includes_evaluation':True,'evaluation_precision':'Per-call E0 wall from retained evaluations.json; supervisor window is the reported inclusive solver wall.','utc':'T0/T1 and supervisor interval from external receipt; OS cold-cache timing not established.'},
       'provenance':{'producer_session':'nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc','task_url':'https://github.com/huaweibei123/huaweicup2026/issues/51',
        'solver':{'source':code(FROZEN,'src/q3/query_flow_solve.py','src.q3.query_flow_solve.main'),'authors':['nikolastar'],'method':'Unified query-flow construction and guarded candidate selection, as executed by the frozen solver entrypoint; this record covers only case 071 at five cores.','references':[],'upstream':[],'selected_algorithm_id':'q3-query-flow-unified','selected_solver_commit':FROZEN},
        'runner':{'source':code(DELIVERY,'results/a/q3-nikolastarx/query-flow-integration-20260925/integration_runner.py','integration_runner.main'),'argv':['python3.14','-B','results/a/q3-nikolastarx/query-flow-integration-20260925/integration_runner.py','--manifest','results/a/q3-nikolastarx/query-flow-integration-20260925/integration-manifest.json'],'working_directory':'.'},
        'environment':{'os':'macOS arm64','cpu':None,'gpu':'none','ram_bytes':None,'python':'3.14.5','dependencies':None,'threads':None,'workers':1,'peak_rss_bytes':None},
        'measurement':{'started_at':start,'finished_at':finish,'seed':None,'repeat_index':0,'cold_start':None,
          'solver_scope':'Complete measured supervisor lifecycle window, including pre-child sampling, runner startup, unified solve/construction/online candidate E0 selection, post-child terminal checks and cleanup. Child T0/T1 are lifecycle markers inside this window; their difference is not solver_wall. OS cold cache not established.',
          'evaluation_scope':'The row-specific final-plan official E0 duration; included in the six-call unified solver window.',
          'budget':{'wall_seconds':600,'candidate_limit':4,'stop_reason':'One unified run completed 4 P3 candidate evaluations and 2 same-plan P2 guard evaluations; zero retries.'},
          'calls':{'solver':1 if problem=='P3' else 0,'E0':calls,'E1':0,'E2':0},'offline_costs':'none for this run; construction, selection, and all six E0 calls were online.','failure':None},'missing_reasons':missing},
       'notes':notes,'source_url':f'https://github.com/{REPO}/blob/{FROZEN}/src/q3/query_flow_solve.py','baseline':base,
       'cache_pair':({'graph_sha256':GRAPH,'config_sha256':CONFIG,'official_sha256':OFFICIAL,'plan_sha256':PLAN_SHA,'cores':5,'route':'E0','result':resultrefs['P2']} if problem=='P3' else None)})
    feed={'schema_version':1,'submission_version':1,'records':records}
    (HERE/'feed.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__': main()
