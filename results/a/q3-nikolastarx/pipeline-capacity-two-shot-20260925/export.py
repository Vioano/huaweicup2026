#!/usr/bin/env python3
"""Export the preserved two-cell P3 capacity-pipeline mechanism batch.
Reads repository evidence and writes only the feed/summary beside this script.
"""
import gzip, hashlib, json
from pathlib import Path

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[3]
REL=OUT.relative_to(REPO)
SOURCE='78d82a99ba00f07e2890c87a7132955369efa73b'
MANIFEST_SHA='7591f1f41ca3eb49401105117b27e9ff9a278727246f7f9d3d3af5b76d44d88b'
RUN_ID='q3-pipeline-capacity-two-20260925-s3172'
SESSION='nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc'
ISSUE='https://github.com/huaweibei123/huaweicup2026/issues/51'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readj(p): return json.loads(p.read_text())
def src(path, entry):
    return {'repo':'huaweibei123/huaweicup2026','commit':SOURCE,'path':path,'entrypoint':entry}

manifest=readj(OUT/'manifest.json'); run=readj(OUT/'run.json')
assert sha(OUT/'manifest.json')==MANIFEST_SHA==run['manifest_sha256']
assert manifest['source_commit']==run['source_commit']==SOURCE
assert run['status']=='complete' and len(run['jobs'])==2
assert run['new_p3_reserved']==2 and run['new_p2']==0 and run['solver_calls']==0
assert run['budget']['retries']==0 and run['budget']['workers']==1
assert [j['case_id'] for j in run['jobs']]==['044','046']
assert [j['cores'] for j in run['jobs']]==[5,5]
assert manifest['official_code_sha256']=='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'

missing={
 'provenance.runner.argv':'Outer runner argv was not retained; exact child evaluator argv is preserved in run.json per job.',
 'provenance.environment.os':'As-run OS was not recorded in manifest/run.',
 'provenance.environment.cpu':'As-run CPU model was not recorded in manifest/run.',
 'provenance.environment.gpu':'GPU use/availability was not recorded in manifest/run.',
 'provenance.environment.ram_bytes':'Total physical RAM was not recorded in manifest/run.',
 'provenance.environment.python':'As-run Python version was not recorded in manifest/run.',
 'provenance.environment.threads':'Thread count was not recorded in manifest/run.',
 'provenance.environment.peak_rss_bytes':'Only sampled process-group RSS values were recorded; they are not actual peaks.',
 'provenance.measurement.solver_scope':'No end-to-end solver was run, so solver wall scope is unavailable.',
 'provenance.measurement.seed':'No random seed is recorded; the capacity construction is deterministic.',
 'provenance.measurement.cold_start':'Cold/warm process and filesystem cache state was not recorded.',
}
lockhash=manifest['source_input_sha256']['uv.lock']
records=[]
for job in run['jobs']:
    case=job['case_id']; core=job['cores']; label=f'{case}-k{core}'
    plan=OUT/job['plan_file']; result_path=OUT/'evaluation'/case/'result.json.gz'
    result=json.loads(gzip.decompress(result_path.read_bytes()))
    assert sha(plan)==job['plan_sha256']
    assert sha(result_path)==job['result_sha256']
    assert result['problem']==3 and result['scene']=='B' and result['cache_mode']=='read_only'
    assert result['num_cores']==core and result['makespan']==job['makespan']
    assert result['data_movement_bytes']==job['movement']
    assert result['cache_stats']==job['cache_stats']
    graphpath=f'data/raw/a/official/data/case_{case}.json'
    identity={'graph_sha256':manifest['source_input_sha256'][graphpath],
      'config_sha256':manifest['source_input_sha256']['data/raw/a/official/data/config.txt'],
      'official_sha256':manifest['official_code_sha256'],'plan_sha256':sha(plan)}
    artifacts={'plan':{'path':(REL/job['plan_file']).as_posix(),'sha256':sha(plan)},
      'result':{'path':(REL/'evaluation'/case/'result.json.gz').as_posix(),'sha256':sha(result_path)},
      'run':{'path':(REL/'run.json').as_posix(),'sha256':sha(OUT/'run.json')},
      'manifest':{'path':(REL/'manifest.json').as_posix(),'sha256':sha(OUT/'manifest.json')}}
    record={'attempt_id':f'nikolastarx-pipeline-capacity-{case}-k{core}-20260925-s3172','revision':1,
      'run_id':RUN_ID,'algorithm_id':'q3-capacity-shared-pipeline',
      'algorithm_name':'Q3 capacity-constrained shared-pipeline mechanism',
      'variant':'capacity-dp-single-plan-one-shot-e0','solver_commit':SOURCE,
      'parameters':{'requested_cores':core,'candidate_count':1,'selection':'single constructed plan per case; no online selection'},
      'problem':'P3','case_id':case,'cores':core,'status':'ok',
      'metrics':{'makespan_cycles':result['makespan'],'solver_wall_seconds':None,
       'evaluation_wall_seconds':job['child']['wall_seconds'],
       'ddr_bytes':result['data_movement_bytes']['scheduled_copy_bytes'],
       'extra_ddr_bytes':result['data_movement_bytes']['added_copy_bytes'],
       'spill_bytes':result['data_movement_bytes']['spill_added_copy_bytes'],
       'cache_hit_rate':result['cache_stats']['hit_rate']},
      'evaluator':{'route':'E0','commit':SOURCE,'entrypoint':'multicore_cut_evaluate_problem_3.evaluate_problem_3'},
      'identity':identity,'artifacts':artifacts,'runtime_id':'unknown','observed_at':run['finished_at'],
      'timing':{'solver_includes_evaluation':False,
       'evaluation_precision':'child wall_seconds preserved from run.json','utc':'UTC timestamps in run.json'},
      'provenance':{'producer_session':SESSION,'task_url':ISSUE,
       'solver':{'source':src('src/q3/shared_pipeline_capacity.py','construct'),'authors':['nikolastarx'],
        'method':'Capacity-constrained dynamic programming constructs one contiguous shared-pipeline partition plan; static mechanism probe, not a general end-to-end solver.',
        'references':[],'upstream':[],'selected_algorithm_id':None,'selected_solver_commit':None},
       'runner':{'source':src('src/q3/pipeline_capacity_probe.py','src.q3.pipeline_capacity_probe'),'argv':[],
        'working_directory':'.'},
       'environment':{'os':None,'cpu':None,'gpu':None,'ram_bytes':None,
        'python':None,'dependencies':f'uv.lock sha256:{lockhash}','threads':None,'workers':1,'peak_rss_bytes':None},
       'measurement':{'started_at':run['started_at'],'finished_at':run['finished_at'],'seed':None,
        'repeat_index':0,'cold_start':None,
        'solver_scope':None,'evaluation_scope':'Independent official P3 E0 subprocess only; this child wall does not include complete solver startup/read/construct/cleanup.',
        'budget':{'wall_seconds':60,'candidate_limit':1,'stop_reason':'One preauthorized P3 E0 completed for this cell; no P2/solver call.'},
        'calls':{'solver':0,'E0':1,'E1':0,'E2':0},
        'offline_costs':f"No training/compilation/precompute; two-case plan preparation took {manifest['prepare_seconds']:.6f} s total, not solver wall.",
        'failure':None},'missing_reasons':dict(missing)},
      'notes':[f"Mechanism-only P3 cell {label}; not a full-suite algorithm score.",
       'solver_wall_seconds is null: no end-to-end solver was executed; preparation timing is not a solver runtime.',
       f"Independent official E0 wall time: {job['child']['wall_seconds']:.9f} s.",
       f"Sampled RSS {job['child']['memory']['sampled_peak_rss_bytes']} bytes is a sampled process-group tripwire observation, not an actual peak.",
       'No P2 cache_pair is included.'],
      'source_url':f"https://github.com/huaweibei123/huaweicup2026/blob/{SOURCE}/src/q3/shared_pipeline_capacity.py"}
    records.append(record)
feed={'schema_version':1,'submission_version':1,'records':records}
f=OUT/'board-feed-20260925T004004Z-s3172.json'
f.write_text(json.dumps(feed,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
summary={'feed':f.name,'feed_sha256':sha(f),'record_count':len(records),'run_id':RUN_ID,
 'manifest_sha256':sha(OUT/'manifest.json'),'current_run_sha256':sha(OUT/'run.json'),
 'records':[{'attempt_id':r['attempt_id'],'case_id':r['case_id'],'cores':r['cores'],
   'makespan_cycles':r['metrics']['makespan_cycles'],'extra_ddr_bytes':r['metrics']['extra_ddr_bytes'],
   'spill_bytes':r['metrics']['spill_bytes'],'cache_hit_rate':r['metrics']['cache_hit_rate'],
   'evaluation_wall_seconds':r['metrics']['evaluation_wall_seconds'],'solver_wall_seconds':None,
   'artifact_hashes':{k:v['sha256'] for k,v in r['artifacts'].items()}} for r in records],
 'scope':'Two measured P3 mechanism cells only; not full500 or complete solver evidence.',
 'environment_note':'As-run OS/CPU/GPU/RAM/Python unavailable from manifest/run and left null with reasons; workers and uv.lock identity were recorded.',
 'preflight_command':'python3 src/benchmark_board/protocol.py '+str(f.relative_to(REPO))+' --repo '+str(REPO.relative_to(REPO.parent))+' --submission',
 'limitations':['Local protocol preflight only; not upload/admission.','No P2 or complete solver run; solver_wall_seconds is null.']}
(OUT/'export-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'feed':str(f),'feed_sha256':sha(f),'records':[{'case_id':r['case_id'],'makespan':r['metrics']['makespan_cycles'],'extra':r['metrics']['extra_ddr_bytes'],'spill':r['metrics']['spill_bytes'],'hit_rate':r['metrics']['cache_hit_rate'],'E0_wall':r['metrics']['evaluation_wall_seconds']} for r in records]},ensure_ascii=False,indent=2))
