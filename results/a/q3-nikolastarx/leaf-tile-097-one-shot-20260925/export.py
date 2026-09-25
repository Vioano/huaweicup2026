#!/usr/bin/env python3
"""Export one preserved leaf-tile P3 mechanism attempt to board-submission-v1.
Read-only with respect to the repository; writes only beside this script.
"""
import gzip, hashlib, json, sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
REL = OUT.relative_to(REPO)
SOURCE = '638ef288bfd287a436095965441bfbd0a2f9d488'
RUN_ID = 'q3-leaf-tile-097-one-shot-20260925-s3172'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def j(path): return json.loads(path.read_text())
def code_source(path):
    return {'repo':'huaweibei123/huaweicup2026','commit':SOURCE,'path':path,
            'entrypoint': 'transform' if path.endswith('leaf_tile.py') else 'src.q3.leaf_tile_probe'}

base = REPO / REL
manifest, run = j(base/'manifest.json'), j(base/'run.json')
result_path, plan_path = base/'evaluation/result.json.gz', base/'plan.json'
result = json.loads(gzip.decompress(result_path.read_bytes()))
assert run['status']=='complete' and run['source_commit']==SOURCE
assert run['budget']==manifest['budget'] and run['solver_calls']==0 and run['new_p2']==0
assert run['child']['status']=='ok' and run['child']['exit_code']==0
assert run['new_p3_reserved']==1 and run['budget']['new_p3']==1 and run['budget']['retries']==0
assert sha(base/'manifest.json')==run['manifest_sha256']
assert sha(plan_path)==run['plan_sha256']==manifest['plan_sha256']
assert sha(result_path)==run['result_sha256']
assert result['problem']==3 and result['scene']=='B' and result['cache_mode']=='read_only' and result['num_cores']==1
assert result['makespan']==run['makespan']
assert manifest['source_input_sha256']['data/raw/a/official/data/case_097.json']=='7dc5c8ebf92052dbdd1bf59794a8fcef74e3ab3c59d5f0b4e753bf38a741ffaf'
assert manifest['source_input_sha256']['data/raw/a/official/data/config.txt']=='dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
assert manifest['official_code_sha256']=='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'

m = result['data_movement_bytes']; c = result['cache_stats']
# Do not report export-time host probes as the environment used for the run.
ram = cpu = osname = pyver = None
lockhash = manifest['source_input_sha256']['uv.lock']
run_rel = (REL/'run.json').as_posix()
missing = {
 'provenance.runner.argv':'Outer runner argv was not retained; [] avoids inventing it, while the official child argv remains recorded in run.json.',
 'provenance.environment.os':'Run receipt does not capture the as-run OS.',
 'provenance.environment.cpu':'Run receipt does not capture the as-run CPU model.',
 'provenance.environment.gpu':'Run receipt does not capture GPU availability/use.',
 'provenance.environment.ram_bytes':'Run receipt does not capture total physical RAM.',
 'provenance.environment.python':'Run receipt does not capture the as-run Python version.',
 'provenance.environment.threads':'Thread count was not recorded by the run receipt.',
 'provenance.measurement.seed':'This deterministic single candidate run has no recorded random seed.',
 'provenance.measurement.cold_start':'Cold/warm process and filesystem cache state was not measured.',
 'provenance.measurement.solver_scope':'No end-to-end solver was run; only one static candidate was constructed and separately evaluated by E0.',
}
missing['provenance.environment.peak_rss_bytes']='Only a sampled process-group RSS tripwire value was retained; it is not an actual peak.'
record = {
 'attempt_id':'nikolastarx-leaf-tile-097-k1-20260925-s3172','revision':1,'run_id':RUN_ID,
 'algorithm_id':'q3-leaf-tile','algorithm_name':'Q3 leaf-tile one-shot mechanism',
 'variant':'static-4x4-single-candidate-no-online-selection','solver_commit':SOURCE,
 'parameters':{'tile_shape':[4,4],'candidate_count':1,'selection':'single static candidate; no online selection','scope':'one P3 E0 mechanism probe'},
 'problem':'P3','case_id':'097','cores':1,'status':'ok',
 'metrics':{'makespan_cycles':result['makespan'],'solver_wall_seconds':None,
   'evaluation_wall_seconds':run['child']['wall_seconds'],'ddr_bytes':m['scheduled_copy_bytes'],
   'extra_ddr_bytes':m['added_copy_bytes'],'spill_bytes':m['spill_added_copy_bytes'],
   'cache_hit_rate':c['hit_rate']},
 'evaluator':{'route':'E0','commit':SOURCE,'entrypoint':'multicore_cut_evaluate_problem_3.evaluate_problem_3'},
 'identity':{'graph_sha256':manifest['source_input_sha256']['data/raw/a/official/data/case_097.json'],
   'config_sha256':manifest['source_input_sha256']['data/raw/a/official/data/config.txt'],
   'official_sha256':manifest['official_code_sha256'],'plan_sha256':sha(plan_path)},
 'artifacts':{
   'plan':{'path':(REL/'plan.json').as_posix(),'sha256':sha(plan_path)},
   'result':{'path':(REL/'evaluation/result.json.gz').as_posix(),'sha256':sha(result_path)},
   'run':{'path':run_rel,'sha256':sha(base/'run.json')},
   'manifest':{'path':(REL/'manifest.json').as_posix(),'sha256':sha(base/'manifest.json')},
   'trace':{'path':(REL/'provenance-derivation.json').as_posix(),'sha256':sha(base/'provenance-derivation.json')}},
 'runtime_id':'unknown','observed_at':run['finished_at'],
 'timing':{'solver_includes_evaluation':False,'evaluation_precision':'child wall_seconds reported to 0.1 ms; preserve source precision','utc':'UTC timestamps in run.json'},
 'provenance':{
   'producer_session':'nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc','task_url':'https://github.com/huaweibei123/huaweicup2026/issues/51',
   'solver':{'source':code_source('src/q3/leaf_tile.py'),'authors':['nikolastarx'],
     'method':'Cartesian leaf-tile transform; one capacity-derived 4x4 candidate, algebraic selection only. Not a general solver or capacity/quality guarantee.',
     'references':[],'upstream':[],'selected_algorithm_id':None,'selected_solver_commit':None},
   'runner':{'source':code_source('src/q3/leaf_tile_probe.py'),'argv':[], 'working_directory':'.'},
   'environment':{'os':osname,'cpu':cpu,'gpu':None,'ram_bytes':ram,
     'python':pyver,'dependencies':f'uv.lock sha256:{lockhash}','threads':None,'workers':1,'peak_rss_bytes':None},
   'measurement':{'started_at':run['started_at'],'finished_at':run['finished_at'],'seed':None,'repeat_index':0,'cold_start':None,
     'solver_scope':None,'evaluation_scope':'Independent official P3 E0 only; child wall_seconds covers official evaluation subprocess, not candidate construction or complete solver.',
     'budget':{'wall_seconds':60,'candidate_limit':1,'stop_reason':'One preauthorized P3 E0 completed; no P2 or solver call.'},
     'calls':{'solver':0,'E0':1,'E1':0,'E2':0},
     'offline_costs':'No training/compilation/precompute. Static candidate construct/validate/write took 0.223203208995983 s per manifest; not solver wall.',
     'failure':None},'missing_reasons':missing},
 'notes':['Single-cell P3 mechanism evidence only; not a full-500 score or full solver timing.',
   'solver_wall_seconds is null because no end-to-end solver was executed; the 0.223 s construction metric excludes solver startup/read/solve/cleanup.',
   'evaluation_wall_seconds is the separate official E0 child wall (1.2912873749737628 s), not solver time.',
   'run.json was privacy-derived after execution; see provenance-derivation artifact. resource_preflight supervisor_sha256 remains the as-run hash.',
   'sampled_peak_rss_bytes=139427840 is a 0.1 s sampled process-group RSS tripwire observation, not an actual peak; peak_rss_bytes remains null.',
   'No baseline included because the official single-core result bytes are absent from this worktree. No P2 cache_pair.'],
 'source_url':f'https://github.com/huaweibei123/huaweicup2026/blob/{SOURCE}/src/q3/leaf_tile.py',
 'baseline':None,'cache_pair':None}
feed={'schema_version':1,'submission_version':1,'records':[record]}
path=OUT/'board-feed-20260925T001030Z-s3172.json'
path.write_text(json.dumps(feed,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'feed':str(path),'feed_sha256':sha(path),'artifact_hashes':{k:v['sha256'] for k,v in record['artifacts'].items()},
 'case':'097','cores':1,'makespan':result['makespan'],'evaluation_wall_seconds':run['child']['wall_seconds'],
 'solver_wall_seconds':None,'baseline':'omitted: worktree baseline bytes absent'},ensure_ascii=False,indent=2))
